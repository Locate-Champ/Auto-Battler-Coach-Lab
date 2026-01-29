"""Manages game state by processing log events."""

from datetime import datetime
from typing import Callable, Optional

from app.watcher.parser import GameEvent, EventType
from .game_state import GameState, GamePhase, PlayerState, Unit


class StateManager:
    """Processes game events and maintains current game state."""

    def __init__(self):
        self.state = GameState()
        self.state_callbacks: list[Callable[[GameState], None]] = []

    def on_state_change(self, callback: Callable[[GameState], None]):
        """Register a callback for state changes."""
        self.state_callbacks.append(callback)

    def _notify_state_change(self):
        """Notify all callbacks of state change."""
        for callback in self.state_callbacks:
            try:
                callback(self.state)
            except Exception as e:
                print(f"Error in state callback: {e}")

    def process_event(self, event: GameEvent):
        """Process a game event and update state."""
        handler = getattr(self, f"_handle_{event.event_type.value}", None)
        if handler:
            handler(event)
            self.state.last_update = event.timestamp
            self._notify_state_change()

    def _handle_game_start(self, event: GameEvent):
        """Handle game start event."""
        self.state.reset()
        self.state.game_phase = GamePhase.LOADING
        self.state.game_start_time = event.timestamp
        print(f"[STATE] Game started at {event.timestamp}")

    def _handle_stage_change(self, event: GameEvent):
        """Handle stage change event."""
        new_stage = event.data.get("stage", "0-0")
        old_stage = self.state.stage
        self.state.stage = new_stage

        # Determine game phase based on stage
        stage_num, round_num = self._parse_stage(new_stage)

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
            print(f"[STATE] Augment armory opened: {options}")
        elif state == "inactive":
            self.state.augment_armory_active = False
            self.state.augment_options = []
            print("[STATE] Augment armory closed")

    def _handle_item_select(self, event: GameEvent):
        """Handle item selection event."""
        items = event.data.get("items", {})
        self.state.game_phase = GamePhase.ITEM_SELECT
        print(f"[STATE] Item selection: {items}")

    def _handle_scouting(self, event: GameEvent):
        """Handle scouting event."""
        player = event.data.get("player", "")
        self.state.currently_scouting = player
        print(f"[STATE] Scouting: {player}")

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
                items = [
                    unit_data.get(f"item_{i}", "")
                    for i in range(1, 4)
                ]
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

        self.state.player.board_units = units
        print(f"[STATE] Board updated: {len(units)} units")

    def _handle_bench_update(self, event: GameEvent):
        """Handle bench update event with bench units."""
        bench_data = event.data.get("bench", {})
        units = []

        for slot_key, unit_data in bench_data.items():
            try:
                # Parse items (filter empty strings)
                items = [
                    unit_data.get(f"item_{i}", "")
                    for i in range(1, 4)
                ]
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
