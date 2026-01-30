"""
Redux Bridge Handler

Processes incoming Redux state updates from the MetaTFT injection script
and updates the game state accordingly.
"""

import json
import logging
from typing import Optional, Callable, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReduxBoardUnit:
    """Unit data from Redux board_pieces."""
    id: str
    character_id: str
    name: str
    stars: int
    items: list[str]
    position: Optional[dict] = None  # {row: int, col: int}


@dataclass
class ReduxPlayerInfo:
    """Player info from Redux 'me' state."""
    gold: str
    health: str
    xp: dict
    rank: str
    summoner_name: str


class ReduxBridgeHandler:
    """
    Handles incoming Redux state messages from the injection script.

    Usage:
        handler = ReduxBridgeHandler()
        handler.on_state_update = my_callback_function

        # When WebSocket receives message:
        handler.process_message(message_json)
    """

    def __init__(self):
        self.on_state_update: Optional[Callable[[dict], None]] = None
        self.last_board_hash: Optional[str] = None
        self.last_bench_hash: Optional[str] = None

    def process_message(self, message: str) -> Optional[dict]:
        """
        Process an incoming Redux state message.

        Args:
            message: JSON string from the injection script

        Returns:
            Parsed state dict if valid, None otherwise
        """
        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Redux message: {e}")
            return None

        if data.get("type") != "redux_state":
            logger.debug(f"Ignoring message type: {data.get('type')}")
            return None

        # Extract and validate data
        state = {
            "timestamp": data.get("timestamp"),
            "board_units": self._parse_board_units(data.get("board_units", [])),
            "bench_units": self._parse_bench_units(data.get("bench_units", [])),
            "player": self._parse_player_info(data.get("me", {})),
            "roster": data.get("roster", {}),
            "opponent_boards": self._parse_all_boards(data.get("board_data", {})),
            "raw": data.get("raw", {}),
        }

        # Check if state actually changed
        current_board_hash = json.dumps(state["board_units"], sort_keys=True)
        current_bench_hash = json.dumps(state["bench_units"], sort_keys=True)

        if (current_board_hash != self.last_board_hash or
            current_bench_hash != self.last_bench_hash):

            self.last_board_hash = current_board_hash
            self.last_bench_hash = current_bench_hash

            logger.info(
                f"Redux state update: {len(state['board_units'])} board units, "
                f"{len(state['bench_units'])} bench units"
            )

            # Notify callback
            if self.on_state_update:
                self.on_state_update(state)

        return state

    def _parse_board_units(self, units: list) -> list[dict]:
        """Parse board units from Redux format."""
        parsed = []
        for unit in units:
            if not isinstance(unit, dict):
                continue
            parsed.append({
                "id": unit.get("id"),
                "character_id": unit.get("character_id", ""),
                "name": unit.get("name", ""),
                "stars": unit.get("stars", 1),
                "items": unit.get("items", []),
                "position": unit.get("position"),
            })
        return parsed

    def _parse_bench_units(self, units: list) -> list[dict]:
        """Parse bench units from Redux format."""
        parsed = []
        for unit in units:
            if not isinstance(unit, dict):
                continue
            parsed.append({
                "id": unit.get("id"),
                "character_id": unit.get("character_id", ""),
                "name": unit.get("name", ""),
                "stars": unit.get("stars", 1),
                "items": unit.get("items", []),
            })
        return parsed

    def _parse_player_info(self, me: dict) -> dict:
        """Parse player info from Redux 'me' state."""
        if not me:
            return {}

        # Parse XP: might be string like "2/6" or dict
        xp = me.get("xp", {})
        if isinstance(xp, str):
            parts = xp.split("/")
            if len(parts) == 2:
                xp = {"current": int(parts[0]), "max": int(parts[1])}

        # Parse health: might be string
        health = me.get("health", "100")
        if isinstance(health, str):
            try:
                health = int(health) if health else 100
            except ValueError:
                health = 100

        return {
            "gold": me.get("gold", "0"),
            "health": health,
            "xp": xp,
            "rank": me.get("rank", ""),
            "summoner_name": me.get("summoner_name", ""),
        }

    def _parse_all_boards(self, board_data: dict) -> dict[str, list[dict]]:
        """
        Parse all 8 players' boards from Redux board_data.

        Args:
            board_data: Dict with keys like "board_0", "board_1", etc.
                       Each value is a dict of position -> unit data

        Returns:
            Dict mapping board_id to list of units on that board
        """
        if not board_data or not isinstance(board_data, dict):
            return {}

        parsed = {}
        for board_key, board_pieces in board_data.items():
            # board_key is like "board_0", "board_1", etc.
            if not board_key.startswith("board_"):
                continue

            if not isinstance(board_pieces, dict):
                continue

            units = []
            for pos_key, unit_data in board_pieces.items():
                if not isinstance(unit_data, dict):
                    continue

                # Parse unit data
                unit = {
                    "character_id": unit_data.get("character_id", ""),
                    "name": unit_data.get("name", ""),
                    "stars": unit_data.get("rarity", 1),  # rarity = star level
                    "items": unit_data.get("items", []),
                    "position": pos_key,
                }
                units.append(unit)

            if units:
                parsed[board_key] = units

        logger.debug(f"Parsed {len(parsed)} opponent boards with {sum(len(u) for u in parsed.values())} total units")
        return parsed


def integrate_with_state_manager(handler: ReduxBridgeHandler, state_manager: Any):
    """
    Connect the Redux bridge handler to the StateManager.

    This sets up the callback so Redux updates flow into the game state.

    Args:
        handler: ReduxBridgeHandler instance
        state_manager: StateManager instance from app/state/state_manager.py
    """
    def on_redux_update(state: dict):
        """Callback when Redux state updates."""
        # Update board units
        if state.get("board_units"):
            from app.state.game_state import Unit
            board_units = []
            for unit_data in state["board_units"]:
                unit = Unit(
                    id=unit_data.get("id"),
                    character_id=unit_data.get("character_id", ""),
                    name=unit_data.get("name", ""),
                    star_level=unit_data.get("stars", 1),
                    items=unit_data.get("items", []),
                    position=unit_data.get("position"),
                )
                board_units.append(unit)
            state_manager.state.player.board_units = board_units

        # Update bench units
        if state.get("bench_units"):
            from app.state.game_state import Unit
            bench_units = []
            for unit_data in state["bench_units"]:
                unit = Unit(
                    id=unit_data.get("id"),
                    character_id=unit_data.get("character_id", ""),
                    name=unit_data.get("name", ""),
                    star_level=unit_data.get("stars", 1),
                    items=unit_data.get("items", []),
                )
                bench_units.append(unit)
            state_manager.state.bench_units = bench_units

        # Update player info
        player = state.get("player", {})
        if player.get("summoner_name"):
            state_manager.state.player.name = player["summoner_name"]
        if player.get("health"):
            state_manager.state.player.health = player["health"]

        # Update opponent boards for pool tracking
        if state.get("opponent_boards"):
            from app.state.game_state import Unit
            opponent_boards = {}
            for board_id, units_data in state["opponent_boards"].items():
                units = []
                for unit_data in units_data:
                    unit = Unit(
                        character_id=unit_data.get("character_id", ""),
                        star_level=unit_data.get("stars", 1),
                        items=unit_data.get("items", []),
                    )
                    units.append(unit)
                opponent_boards[board_id] = units
            state_manager.state.opponent_boards = opponent_boards
            logger.debug(f"Updated {len(opponent_boards)} opponent boards")

        # Mark state as updated
        state_manager.state.update_timestamp()

        logger.debug("State manager updated from Redux bridge")

    handler.on_state_update = on_redux_update
    logger.info("Redux bridge connected to state manager")
