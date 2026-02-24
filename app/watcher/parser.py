"""Parser for MetaTFT log events."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class EventType(Enum):
    """Types of game events we can detect."""

    STAGE_CHANGE = "stage_change"
    XP_CHANGE = "xp_change"
    HEALTH_UPDATE = "health_update"
    AUGMENT_ARMORY = "augment_armory"
    AUGMENT_SELECTED = "augment_selected"
    ITEM_SELECT = "item_select"
    SCOUTING = "scouting"
    WIN_CHANCE = "win_chance"
    GAME_START = "game_start"
    GAME_END = "game_end"
    SHOP_UPDATE = "shop_update"
    BOARD_UPDATE = "board_update"
    BENCH_UPDATE = "bench_update"
    ROSTER_UPDATE = "roster_update"
    UNKNOWN = "unknown"


@dataclass
class GameEvent:
    """Represents a parsed game event."""

    event_type: EventType
    timestamp: datetime
    data: dict = field(default_factory=dict)
    raw_line: str = ""

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


class LogParser:
    """Parses MetaTFT log lines into structured events."""

    # Regex patterns for different event types
    PATTERNS = {
        # Stage change: [EVT] stage: 2-1
        "stage": re.compile(r"\[EVT\] stage: (\d+-\d+)"),
        # XP change: XP: 0/6 -> 2/6
        "xp": re.compile(r"XP: (\d+/\d+) -> (\d+/\d+)"),
        # Health correction: Correcting health for player: Name 93 100
        "health": re.compile(r"Correcting health for player: (.+?) (\d+) (\d+)"),
        # Win chance: WinChanceNumber: ~96%
        "win_chance": re.compile(r"WinChanceNumber:\s+~?(\d+)%"),
        # Scouting: Scouting: PlayerName
        "scouting": re.compile(r"Scouting: (.+)$"),
        # Augment armory JSON
        "augment_armory": re.compile(r"\[AugmentStats\] augment_armory data: ({.+?}) ({.+})"),
        # Item select JSON
        "item_select": re.compile(r"\[ItemStats\] item_select data: ({.+})"),
        # Game start indicators
        "game_start": re.compile(
            r"(TFT starting|GameEventManager\.setGameStarted|registered features.+board)"
        ),
        # Timestamp at start of log line: 2026-01-23 19:20:53,124
        "timestamp": re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"),
        # New stage
        "new_stage": re.compile(r'New Stage: "(\d+-\d+)"'),
        # First shop indicator
        "first_shop": re.compile(r"First Shop"),
        # Generic key/value event payload: "key":"...","value":"{...escaped-json...}"
        # Captures escaped quoted payloads robustly, including nested braces.
        "kv_payload": re.compile(
            r'"key"\s*:\s*"(?P<key>[^"]+)"\s*,\s*"value"\s*:\s*"(?P<value>(?:\\.|[^"\\])*)"'
        ),
    }

    @staticmethod
    def _extract_kv_payload(line: str, key: str) -> Optional[Any]:
        for match in LogParser.PATTERNS["kv_payload"].finditer(line):
            if match.group("key") != key:
                continue

            raw_escaped = match.group("value")
            try:
                # Decode escaped JSON string content first (e.g. {\"cell_1\":...}).
                decoded = json.loads(f'"{raw_escaped}"')
            except json.JSONDecodeError:
                continue

            try:
                return json.loads(decoded)
            except json.JSONDecodeError:
                continue
        return None

    def parse_line(self, line: str) -> Optional[GameEvent]:
        """Parse a single log line and return a GameEvent if relevant."""
        if not line.strip():
            return None

        # Extract timestamp
        timestamp = self._extract_timestamp(line)

        # Try each pattern
        if match := self.PATTERNS["stage"].search(line):
            return GameEvent(
                event_type=EventType.STAGE_CHANGE,
                timestamp=timestamp,
                data={"stage": match.group(1)},
                raw_line=line,
            )

        if match := self.PATTERNS["new_stage"].search(line):
            return GameEvent(
                event_type=EventType.STAGE_CHANGE,
                timestamp=timestamp,
                data={"stage": match.group(1)},
                raw_line=line,
            )

        if match := self.PATTERNS["xp"].search(line):
            return GameEvent(
                event_type=EventType.XP_CHANGE,
                timestamp=timestamp,
                data={
                    "from": match.group(1),
                    "to": match.group(2),
                },
                raw_line=line,
            )

        if match := self.PATTERNS["health"].search(line):
            return GameEvent(
                event_type=EventType.HEALTH_UPDATE,
                timestamp=timestamp,
                data={
                    "player": match.group(1),
                    "old_health": int(match.group(2)),
                    "new_health": int(match.group(3)),
                },
                raw_line=line,
            )

        if match := self.PATTERNS["win_chance"].search(line):
            return GameEvent(
                event_type=EventType.WIN_CHANCE,
                timestamp=timestamp,
                data={"win_chance": int(match.group(1))},
                raw_line=line,
            )

        if match := self.PATTERNS["scouting"].search(line):
            return GameEvent(
                event_type=EventType.SCOUTING,
                timestamp=timestamp,
                data={"player": match.group(1).strip()},
                raw_line=line,
            )

        if match := self.PATTERNS["augment_armory"].search(line):
            try:
                options_data = json.loads(match.group(1))
                selected_data = json.loads(match.group(2))
                return GameEvent(
                    event_type=EventType.AUGMENT_ARMORY,
                    timestamp=timestamp,
                    data={
                        "options": options_data.get("augment_options", []),
                        "state": options_data.get("armory_state", "unknown"),
                        "type": options_data.get("armory_type", "regular"),
                        "selected": selected_data,
                    },
                    raw_line=line,
                )
            except json.JSONDecodeError:
                pass

        if match := self.PATTERNS["item_select"].search(line):
            try:
                items_data = json.loads(match.group(1))
                return GameEvent(
                    event_type=EventType.ITEM_SELECT,
                    timestamp=timestamp,
                    data={"items": items_data},
                    raw_line=line,
                )
            except json.JSONDecodeError:
                pass

        if match := self.PATTERNS["game_start"].search(line):
            return GameEvent(
                event_type=EventType.GAME_START,
                timestamp=timestamp,
                data={"indicator": match.group(1)},
                raw_line=line,
            )

        if self.PATTERNS["first_shop"].search(line):
            return GameEvent(
                event_type=EventType.GAME_START,
                timestamp=timestamp,
                data={"indicator": "first_shop"},
                raw_line=line,
            )

        # Board update: tft_board with cell positions
        board_data = self._extract_kv_payload(line, "tft_board")
        if board_data is not None:
            return GameEvent(
                event_type=EventType.BOARD_UPDATE,
                timestamp=timestamp,
                data={"board": board_data},
                raw_line=line,
            )

        # Bench update: tft_bench with slot positions
        bench_data = self._extract_kv_payload(line, "tft_bench")
        if bench_data is not None:
            return GameEvent(
                event_type=EventType.BENCH_UPDATE,
                timestamp=timestamp,
                data={"bench": bench_data},
                raw_line=line,
            )

        # Shop update: tft_shop with store offerings
        shop_data = self._extract_kv_payload(line, "tft_shop")
        if shop_data is not None:
            return GameEvent(
                event_type=EventType.SHOP_UPDATE,
                timestamp=timestamp,
                data={"shop": shop_data},
                raw_line=line,
            )

        # Roster update: tft_roster with all players
        roster_data = self._extract_kv_payload(line, "tft_roster")
        if roster_data is not None:
            return GameEvent(
                event_type=EventType.ROSTER_UPDATE,
                timestamp=timestamp,
                data={"roster": roster_data},
                raw_line=line,
            )

        return None

    def _extract_timestamp(self, line: str) -> datetime:
        """Extract timestamp from log line."""
        if match := self.PATTERNS["timestamp"].match(line):
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S,%f")
            except ValueError:
                pass
        return datetime.now()

    def parse_lines(self, lines: list[str]) -> list[GameEvent]:
        """Parse multiple lines and return all detected events."""
        events = []
        for line in lines:
            if event := self.parse_line(line):
                events.append(event)
        return events
