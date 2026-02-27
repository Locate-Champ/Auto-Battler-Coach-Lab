"""Manages game state by processing log events."""

import re
import threading
from datetime import datetime
from typing import Callable

from app.watcher.parser import GameEvent

from .game_state import GamePhase, GameState, PlayerState, ShopUnit, Unit


class StateManager:
    """Processes game events and maintains current game state."""

    def __init__(self):
        self.state = GameState()
        self.state_callbacks: list[Callable[[GameState], None]] = []
        self._previous_phase = self.state.game_phase
        self._lock = threading.Lock()

    def on_state_change(self, callback: Callable[[GameState], None]):
        """Register a callback for state changes."""
        self.state_callbacks.append(callback)

    def _notify_state_change(self):
        """Notify all callbacks of state change."""
        for callback in self.state_callbacks:
            try:
                callback(self.state)
            except (ValueError, KeyError, TypeError, AttributeError, RuntimeError) as e:
                print(f"Error in state callback: {e}")

    def process_event(self, event: GameEvent):
        """Process a game event and update state."""
        handler = getattr(self, f"_handle_{event.event_type.value}", None)
        if handler:
            with self._lock:
                handler(event)
                self.state.last_update = event.timestamp
            self._notify_state_change()

    def _handle_game_start(self, event: GameEvent):
        """Handle game start event."""
        self.state.reset()
        self.state.game_phase = GamePhase.LOADING
        self.state.game_start_time = event.timestamp
        self._previous_phase = self.state.game_phase
        print(f"[STATE] Game started at {event.timestamp}")

    def _handle_stage_change(self, event: GameEvent):
        """Handle stage change event."""
        new_stage = event.data.get("stage", "0-0")
        old_stage = self.state.stage
        self.state.stage = new_stage

        # Determine game phase based on stage
        stage_num, round_num = self._parse_stage(new_stage)
        previous_phase = self.state.game_phase

        if stage_num == 0:
            self.state.game_phase = GamePhase.LOADING
        elif round_num == 4 and stage_num >= 2:
            # Round 4 of stage 2+ is typically carousel
            self.state.game_phase = GamePhase.CAROUSEL
        elif round_num <= 3 and stage_num == 1:
            # Stage 1 rounds 1-3 are PvE
            self.state.game_phase = GamePhase.PVE
        else:
            self.state.game_phase = GamePhase.PVP

        if self.state.game_phase == GamePhase.CAROUSEL and previous_phase != GamePhase.CAROUSEL:
            self._record_evaluation_checkpoint(event.timestamp, "carousel")

        if previous_phase == GamePhase.PVE and self.state.game_phase == GamePhase.PVP:
            self._record_evaluation_checkpoint(event.timestamp, "pve_complete")

        self._previous_phase = self.state.game_phase
        print(f"[STATE] Stage: {old_stage} -> {new_stage} (Phase: {self.state.game_phase.value})")

    def _handle_xp_change(self, event: GameEvent):
        """Handle XP change event."""
        old_xp = self.state.xp
        new_xp = event.data.get("to", "0/0")
        self.state.xp = new_xp

        # Detect level up from XP
        old_level = self._get_level_from_xp(old_xp)
        new_level = self._get_level_from_xp(new_xp)

        if new_level > old_level:
            self.state.player.level = new_level
            print(f"[STATE] Level up! {old_level} -> {new_level}")

    def _handle_health_update(self, event: GameEvent):
        """Handle health update event."""
        player_name = event.data.get("player", "")
        new_health = event.data.get("new_health", 100)

        # Check if this is our player
        if self.state.player.name and player_name.lower() == self.state.player.name.lower():
            old_health = self.state.player.health
            self.state.player.health = new_health
            print(f"[STATE] Health: {old_health} -> {new_health}")
        else:
            # Update opponent health
            if player_name not in self.state.opponents:
                self.state.opponents[player_name] = PlayerState(name=player_name)
            self.state.opponents[player_name].health = new_health

    def _handle_augment_armory(self, event: GameEvent):
        """Handle augment armory event."""
        options = event.data.get("options", [])
        state = event.data.get("state", "")

        if state == "active" and options:
            self.state.augment_armory_active = True
            self.state.augment_options = options
            self.state.game_phase = GamePhase.AUGMENT
            self._previous_phase = self.state.game_phase
            print(f"[STATE] Augment armory opened: {options}")
        elif state == "inactive":
            if self.state.augment_armory_active:
                self._record_evaluation_checkpoint(event.timestamp, "augment_complete")
            self.state.augment_armory_active = False
            self.state.augment_options = []
            if self.state.game_phase == GamePhase.AUGMENT:
                self.state.game_phase = GamePhase.PVP
            self._previous_phase = self.state.game_phase
            print("[STATE] Augment armory closed")

    def _record_evaluation_checkpoint(self, timestamp: datetime, reason: str):
        """Record a checkpoint for evaluation timing."""
        self.state.evaluation_checkpoints.append(
            {
                "timestamp": timestamp.isoformat(),
                "stage": self.state.stage,
                "phase": self.state.game_phase.value,
                "reason": reason,
            }
        )

    def _handle_item_select(self, event: GameEvent):
        """Handle item selection event."""
        items = event.data.get("items", {})
        self.state.game_phase = GamePhase.ITEM_SELECT

        unassigned: list[str] = []
        if isinstance(items, dict):
            for _, item_data in items.items():
                if isinstance(item_data, dict):
                    name = item_data.get("name") or item_data.get("api_name") or item_data.get("id")
                    if isinstance(name, str) and name:
                        unassigned.append(name)
                elif isinstance(item_data, str) and item_data:
                    unassigned.append(item_data)

        if unassigned:
            self.state.unassigned_items = unassigned
        print(f"[STATE] Item selection: {items}")

    def _handle_scouting(self, event: GameEvent):
        """Handle scouting event."""
        player = (event.data.get("player", "") or "").strip()
        if not player:
            self.state.currently_scouting = None
        elif self.state.player.name and player.lower() == self.state.player.name.lower():
            self.state.currently_scouting = None
        else:
            self.state.currently_scouting = player
        print(f"[STATE] Scouting: {self.state.currently_scouting or 'self'}")

    def _handle_win_chance(self, event: GameEvent):
        """Handle win chance prediction event."""
        win_chance = event.data.get("win_chance", 0)
        self.state.win_chance = win_chance

    def _handle_board_update(self, event: GameEvent):
        """Handle board update event with unit positions."""
        board_data = event.data.get("board", {})
        units = []

        for cell_key, unit_data in board_data.items():
            try:
                # Parse cell_X to get position
                cell_id = int(cell_key.replace("cell_", ""))
                row = cell_id // 7
                col = cell_id % 7

                # Parse items (filter empty strings)
                items = [unit_data.get(f"item_{i}", "") for i in range(1, 4)]
                items = [item for item in items if item]

                # Create Unit
                unit = Unit(
                    character_id=unit_data.get("name", ""),
                    star_level=int(unit_data.get("level", "1")),
                    items=items,
                    position=(row, col),
                )
                units.append(unit)
            except (ValueError, KeyError) as e:
                print(f"[STATE] Error parsing board unit {cell_key}: {e}")

        if self.state.currently_scouting:
            self.state.opponent_boards[self.state.currently_scouting] = units
            print(
                f"[STATE] Scouted board updated: {self.state.currently_scouting} ({len(units)} units)"
            )
        else:
            self.state.player.board_units = units
            print(f"[STATE] Board updated: {len(units)} units")

    def _handle_bench_update(self, event: GameEvent):
        """Handle bench update event with bench units."""
        bench_data = event.data.get("bench", {})
        units = []

        for slot_key, unit_data in bench_data.items():
            try:
                # Parse items (filter empty strings)
                items = [unit_data.get(f"item_{i}", "") for i in range(1, 4)]
                items = [item for item in items if item]

                # Create Unit (no position for bench)
                unit = Unit(
                    character_id=unit_data.get("name", ""),
                    star_level=int(unit_data.get("level", "1")),
                    items=items,
                    position=None,
                )
                units.append(unit)
            except (ValueError, KeyError) as e:
                print(f"[STATE] Error parsing bench unit {slot_key}: {e}")

        self.state.bench_units = units
        print(f"[STATE] Bench updated: {len(units)} units")

    def _handle_shop_update(self, event: GameEvent):
        """Handle shop update event with shop offerings."""
        shop_data = event.data.get("shop", {})
        units: list[ShopUnit] = []

        if isinstance(shop_data, dict):
            for _, unit_data in shop_data.items():
                if isinstance(unit_data, dict):
                    character_id = unit_data.get("name") or unit_data.get("character_id") or ""
                    cost_raw = (
                        unit_data.get("cost") or unit_data.get("tier") or unit_data.get("price")
                    )
                elif isinstance(unit_data, str):
                    character_id = unit_data
                    cost_raw = None
                else:
                    continue

                if not isinstance(character_id, str) or not character_id:
                    continue

                cost = None
                if cost_raw is not None:
                    try:
                        cost = int(cost_raw)
                    except (TypeError, ValueError):
                        cost = None

                units.append(ShopUnit(character_id=character_id, cost=cost))

        self.state.shop_units = units
        if units:
            print(f"[STATE] Shop updated: {len(units)} units")

    def _handle_roster_update(self, event: GameEvent):
        """Handle roster update event with all 8 players."""
        roster_data = event.data.get("roster", [])

        for player_data in roster_data:
            try:
                name = player_data.get("summoner", "")
                is_local = player_data.get("localplayer") == "1"
                health = int(player_data.get("health", "100"))
                xp = int(player_data.get("xp", "1"))

                if is_local:
                    # Update our player
                    self.state.player.name = name
                    self.state.player.health = health
                    # XP is already tracked via xp_change events
                else:
                    # Update opponent
                    if name not in self.state.opponents:
                        self.state.opponents[name] = PlayerState(name=name)
                    self.state.opponents[name].health = health

            except (ValueError, KeyError) as e:
                print(f"[STATE] Error parsing roster player: {e}")

    def _parse_stage(self, stage: str) -> tuple[int, int]:
        """Parse stage string into (stage_num, round_num)."""
        try:
            parts = stage.split("-")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return 0, 0

    def _get_level_from_xp(self, xp: str) -> int:
        """Infer level from XP string."""
        # XP thresholds: 0/2, 0/2, 0/6, 0/10, 0/20, 0/36, 0/56, 0/80, 0/84
        thresholds = {2: 2, 6: 3, 10: 4, 20: 5, 36: 6, 56: 7, 80: 8, 84: 9}
        try:
            parts = xp.split("/")
            max_xp = int(parts[1])
            return thresholds.get(max_xp, 1)
        except (ValueError, IndexError):
            return 1

    def get_state(self) -> GameState:
        """Get current game state."""
        return self.state

    def get_state_dict(self) -> dict:
        """Get current game state as dictionary."""
        return self.state.to_dict()

    def apply_redux_state(self, redux_state: dict) -> None:
        """Apply a Redux bridge snapshot into the live GameState."""
        now = datetime.now()

        # Timestamp (best effort).
        last_update = now
        ts = redux_state.get("timestamp")
        if isinstance(ts, str) and ts:
            try:
                last_update = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                last_update = now

        player = redux_state.get("player") if isinstance(redux_state.get("player"), dict) else {}

        with self._lock:
            self.state.last_update = last_update

            # Player identity + vitals
            name = player.get("summoner_name")
            if isinstance(name, str) and name:
                self.state.player.name = name

            health = player.get("health")
            if isinstance(health, int):
                self.state.player.health = health
            elif isinstance(health, str) and health:
                try:
                    self.state.player.health = int(health)
                except ValueError:
                    pass

            gold = player.get("gold")
            if isinstance(gold, int):
                self.state.gold = gold
            elif isinstance(gold, str):
                try:
                    self.state.gold = int(gold) if gold else 0
                except ValueError:
                    pass

            # XP as "cur/max" to reuse existing level inference logic.
            xp = player.get("xp")
            if isinstance(xp, dict):
                cur = xp.get("current")
                mx = xp.get("max")
                try:
                    cur_i = int(cur)
                    mx_i = int(mx)
                    self.state.xp = f"{cur_i}/{mx_i}"
                    self.state.player.level = self._get_level_from_xp(self.state.xp)
                except (ValueError, TypeError):
                    pass
            elif isinstance(xp, str) and xp:
                self.state.xp = xp
                self.state.player.level = self._get_level_from_xp(self.state.xp)

            # Board units
            board_units_raw = redux_state.get("board_units")
            if isinstance(board_units_raw, list):
                board_units: list[Unit] = []
                for unit_data in board_units_raw:
                    if not isinstance(unit_data, dict):
                        continue
                    pos = unit_data.get("position")
                    pos_tuple = None
                    if isinstance(pos, dict):
                        try:
                            pos_tuple = (int(pos.get("row")), int(pos.get("col")))
                        except (ValueError, TypeError):
                            pos_tuple = None
                    board_units.append(
                        Unit(
                            character_id=str(unit_data.get("character_id") or ""),
                            star_level=int(unit_data.get("stars") or 1),
                            items=list(unit_data.get("items") or []),
                            position=pos_tuple,
                        )
                    )
                self.state.player.board_units = board_units

            # Bench units
            bench_units_raw = redux_state.get("bench_units")
            if isinstance(bench_units_raw, list):
                bench_units: list[Unit] = []
                for unit_data in bench_units_raw:
                    if not isinstance(unit_data, dict):
                        continue
                    bench_units.append(
                        Unit(
                            character_id=str(unit_data.get("character_id") or ""),
                            star_level=int(unit_data.get("stars") or 1),
                            items=list(unit_data.get("items") or []),
                            position=None,
                        )
                    )
                self.state.bench_units = bench_units

            # Shop units
            shop_units_raw = redux_state.get("shop_units")
            shop_units: list[ShopUnit] = []
            if isinstance(shop_units_raw, list):
                for su in shop_units_raw:
                    if isinstance(su, dict):
                        cid = su.get("character_id")
                        cost_raw = su.get("cost")
                    elif isinstance(su, str):
                        cid = su
                        cost_raw = None
                    else:
                        continue

                    if not isinstance(cid, str) or not cid:
                        continue

                    cost = None
                    if cost_raw is not None:
                        try:
                            cost = int(cost_raw)
                        except (TypeError, ValueError):
                            cost = None
                    shop_units.append(ShopUnit(character_id=cid, cost=cost))

            # Back-compat: parse raw shop_pieces when inject.js only sends raw.shop
            if not shop_units:
                raw = redux_state.get("raw") if isinstance(redux_state.get("raw"), dict) else {}
                raw_shop = raw.get("shop")
                if isinstance(raw_shop, dict):
                    for _, unit_data in raw_shop.items():
                        if not isinstance(unit_data, dict):
                            continue
                        cid = unit_data.get("name") or unit_data.get("character_id")
                        if not isinstance(cid, str) or not cid:
                            continue
                        shop_units.append(ShopUnit(character_id=cid, cost=None))

            self.state.shop_units = shop_units

            # Opponent boards (for pool tracking and coach tempo robustness)
            opponent_boards = redux_state.get("opponent_boards")
            if isinstance(opponent_boards, dict):
                parsed: dict[str, list[Unit]] = {}
                pos_re = re.compile(r"^([A-Da-d])([0-9])$")
                for board_id, units_data in opponent_boards.items():
                    if not isinstance(units_data, list):
                        continue
                    units: list[Unit] = []
                    for unit_data in units_data:
                        if not isinstance(unit_data, dict):
                            continue
                        cid = unit_data.get("character_id") or unit_data.get("name") or ""
                        stars_raw = unit_data.get("stars") or unit_data.get("level") or 1
                        try:
                            stars = int(stars_raw)
                        except (ValueError, TypeError):
                            stars = 1

                        pos_tuple = None
                        pos_raw = unit_data.get("position")
                        if isinstance(pos_raw, str):
                            m = pos_re.match(pos_raw.strip())
                            if m:
                                row = ord(m.group(1).upper()) - ord("A")
                                col = int(m.group(2)) - 1
                                pos_tuple = (row, col)
                        elif isinstance(pos_raw, dict):
                            try:
                                pos_tuple = (int(pos_raw.get("row")), int(pos_raw.get("col")))
                            except (ValueError, TypeError):
                                pos_tuple = None

                        units.append(
                            Unit(
                                character_id=str(cid),
                                star_level=stars,
                                items=list(unit_data.get("items") or []),
                                position=pos_tuple,
                            )
                        )
                    if units:
                        parsed[str(board_id)] = units
                if parsed:
                    self.state.opponent_boards = parsed

        self._notify_state_change()
