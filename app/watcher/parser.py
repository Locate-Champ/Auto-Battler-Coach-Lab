"""Parser for MetaTFT log events."""

import re
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from enum import Enum


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
        "augment_armory": re.compile(r'\[AugmentStats\] augment_armory data: ({.+?}) ({.+})'),

        # Item select JSON
        "item_select": re.compile(r'\[ItemStats\] item_select data: ({.+})'),

        # Game start indicators
        "game_start": re.compile(r"(TFT starting|GameEventManager\.setGameStarted|registered features.+board)"),

        # Timestamp at start of log line: 2026-01-23 19:20:53,124
        "timestamp": re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"),

        # New stage
        "new_stage": re.compile(r'New Stage: "(\d+-\d+)"'),

        # First shop indicator
        "first_shop": re.compile(r"First Shop"),

        # Board state: tft_board with cell data
        # Matches: "key":"tft_board","value":"{\"cell_1\":{...},...}"
        "board": re.compile(r'"key":"tft_board","value":"(\{[^}]+(?:\}[^}]+)*\})"'),

        # Bench state: tft_bench with slot data
        "bench": re.compile(r'"key":"tft_bench","value":"(\{[^}]+(?:\}[^}]+)*\})"'),

        # Shop state: tft_shop with current shop offerings
        "shop": re.compile(r'"key":"tft_shop","value":"(\{[^}]+(?:\}[^}]+)*\})"'),

        # Roster state: tft_roster with all 8 players
        "roster": re.compile(r'"key":"tft_roster","value":"(\[[^\]]+\])"'),
    }

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
        if match := self.PATTERNS["board"].search(line):
            try:
                # The value is escaped JSON, need to unescape it
                board_json = match.group(1).replace('\\"', '"')
                board_data = json.loads(board_json)
                return GameEvent(
                    event_type=EventType.BOARD_UPDATE,
                    timestamp=timestamp,
                    data={"board": board_data},
                    raw_line=line,
                )
            except json.JSONDecodeError:
                pass

        # Bench update: tft_bench with slot positions
        if match := self.PATTERNS["bench"].search(line):
            try:
                bench_json = match.group(1).replace('\\"', '"')
                bench_data = json.loads(bench_json)
                return GameEvent(
                    event_type=EventType.BENCH_UPDATE,
                    timestamp=timestamp,
                    data={"bench": bench_data},
                    raw_line=line,
                )
            except json.JSONDecodeError:
                pass

        # Shop update: tft_shop with store offerings
        if match := self.PATTERNS["shop"].search(line):
            try:
                shop_json = match.group(1).replace('\\"', '"')
                shop_data = json.loads(shop_json)
                return GameEvent(
                    event_type=EventType.SHOP_UPDATE,
                    timestamp=timestamp,
                    data={"shop": shop_data},
                    raw_line=line,
                )
            except json.JSONDecodeError:
                pass

        # Roster update: tft_roster with all 8 players
        if match := self.PATTERNS["roster"].search(line):
            try:
                roster_json = match.group(1).replace('\\"', '"')
                roster_data = json.loads(roster_json)
                return GameEvent(
                    event_type=EventType.ROSTER_UPDATE,
                    timestamp=timestamp,
                    data={"roster": roster_data},
                    raw_line=line,
                )
            except json.JSONDecodeError:
                pass

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
