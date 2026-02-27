"""Data collector for TFT game simulations.

Hooks into TFTGame to capture per-round state snapshots, combat results,
and final placements for ML training data and balance analytics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from .game import TFTGame


class GameCollector:
    """Collects ML training data + balance analytics from a single game."""

    def __init__(self, game_id: int):
        self.game_id = game_id
        self.rounds: List[Dict] = []
        self.placements: List[Dict] = []
        self._round_data_by_round: Dict[int, Dict] = {}

    def on_round_start(self, game: "TFTGame", round_num: int):
        """Called after matchmaking and before combat resolves."""
        round_data = {
            "round": round_num,
            "alive_count": len(game.alive_players),
            "players": [],
            "combats": [],
        }

        for player in game.players:
            if not player.alive:
                continue
            board_champs = []
            for (r, c), ch in player.board.items():
                board_champs.append(
                    {
                        "name": ch.name,
                        "api_name": ch.api_name,
                        "star": ch.star_level,
                        "items": tuple(ch.items),
                        "pos": (r, c),
                    }
                )

            round_data["players"].append(
                {
                    "id": player.player_id,
                    "hp": player.hp,
                    "gold": player.gold,
                    "level": player.level,
                    "board": board_champs,
                    "board_count": player.board_count,
                    "traits": player.get_active_traits(),
                    "augments": game.player_augments.get(player.player_id, []),
                    "win_streak": player.win_streak,
                    "loss_streak": player.loss_streak,
                }
            )

        self.rounds.append(round_data)
        self._round_data_by_round[round_num] = round_data

    def on_round_end(self, game: "TFTGame", round_num: int, combat_results: List[Dict]):
        """Called after each PvP round.

        Args:
            game: The TFTGame instance.
            round_num: Current round number.
            combat_results: List of combat result dicts from this round.
        """
        round_data = self._round_data_by_round.get(round_num)
        if round_data is None:
            self.on_round_start(game, round_num)
            round_data = self._round_data_by_round.get(round_num)
        if round_data is None:
            return
        round_data["combats"] = combat_results

    def on_game_end(self, game: "TFTGame"):
        """Called when the game finishes."""
        for player_id, placement in game.placements:
            player = game.players[player_id]
            # Final board composition
            board_champs = []
            for (_r, _c), ch in player.board.items():
                board_champs.append(
                    {
                        "name": ch.name,
                        "api_name": ch.api_name,
                        "star": ch.star_level,
                        "items": tuple(ch.items),
                    }
                )

            self.placements.append(
                {
                    "player_id": player_id,
                    "placement": placement,
                    "level": player.level,
                    "hp": player.hp,
                    "board": board_champs,
                    "traits": player.get_active_traits(),
                    "augments": game.player_augments.get(player_id, []),
                }
            )

    def to_dict(self) -> Dict:
        """Serialize collected data to a dict."""
        return {
            "game_id": self.game_id,
            "num_rounds": len(self.rounds),
            "placements": self.placements,
            "rounds": self.rounds,
        }

    def get_training_rows(self) -> List[Dict]:
        """Extract flat ML training rows (one per player per round).

        Each row contains the player's state at round N and their
        final placement as the label. This is the format needed for
        supervised learning (predict placement from board state).
        """
        # Build placement lookup
        placement_map = {p["player_id"]: p["placement"] for p in self.placements}

        rows = []
        for round_data in self.rounds:
            players_by_id = {player["id"]: player for player in round_data["players"]}

            # Build per-player combat metadata from matchup records
            combat_by_player: Dict[int, Dict] = {}
            for combat in round_data.get("combats", []):
                p1 = combat.get("p1")
                p2 = combat.get("p2")
                winner = combat.get("winner")
                damage = combat.get("damage", 0)
                survivors = int(combat.get("survivors", 0) or 0)
                combat_time = float(combat.get("combat_time", 0.0) or 0.0)
                is_ghost = bool(combat.get("is_ghost", False))
                if p1 is None or p2 is None:
                    continue

                is_draw = winner not in (p1, p2)
                pairs = ((p1, p2),) if is_ghost else ((p1, p2), (p2, p1))
                for player_id, opponent_id in pairs:
                    if is_draw:
                        combat_result = 2
                        damage_dealt = 0.0
                        damage_taken = float(damage)
                        player_survivors = 0
                    elif winner == player_id:
                        combat_result = 1
                        damage_dealt = float(damage)
                        damage_taken = 0.0
                        player_survivors = survivors
                    else:
                        combat_result = 0
                        damage_dealt = 0.0
                        damage_taken = float(damage)
                        player_survivors = 0

                    combat_by_player[player_id] = {
                        "opponent_id": opponent_id,
                        "combat_result": combat_result,
                        "damage_dealt": damage_dealt,
                        "damage_taken": damage_taken,
                        "combat_time": combat_time,
                        "survivors": player_survivors,
                        "is_ghost": is_ghost,
                    }

            for player_state in round_data["players"]:
                pid = player_state["id"]
                matchup = combat_by_player.get(pid, {})
                opponent_id = matchup.get("opponent_id")
                opponent_state = players_by_id.get(opponent_id)

                units = []
                for unit in player_state["board"]:
                    position = unit.get("pos")
                    if isinstance(position, (list, tuple)) and len(position) == 2:
                        hex_pos = int(position[0]) * 7 + int(position[1])
                    else:
                        hex_pos = None
                    units.append(
                        {
                            "champion_id": unit.get("api_name", unit.get("name")),
                            "star_level": unit.get("star", 1),
                            "items": unit.get("items", []),
                            "position": hex_pos,
                        }
                    )

                opponent_units = []
                opponent_traits = {}
                opponent_hp = 0
                opponent_gold = 0
                opponent_level = 0
                opponent_win_streak = 0
                opponent_loss_streak = 0
                opponent_board_count = 0
                opponent_augments = []
                opponent_num_augments = 0
                opponent_num_traits = 0
                if opponent_state is not None:
                    for unit in opponent_state.get("board", []):
                        position = unit.get("pos")
                        if isinstance(position, (list, tuple)) and len(position) == 2:
                            hex_pos = int(position[0]) * 7 + int(position[1])
                        else:
                            hex_pos = None
                        opponent_units.append(
                            {
                                "champion_id": unit.get("api_name", unit.get("name")),
                                "star_level": unit.get("star", 1),
                                "items": unit.get("items", []),
                                "position": hex_pos,
                            }
                        )
                    opponent_traits = opponent_state.get("traits", {})
                    opponent_hp = opponent_state.get("hp", 0)
                    opponent_gold = opponent_state.get("gold", 0)
                    opponent_level = opponent_state.get("level", 0)
                    opponent_win_streak = opponent_state.get("win_streak", 0)
                    opponent_loss_streak = opponent_state.get("loss_streak", 0)
                    opponent_board_count = opponent_state.get("board_count", 0)
                    opponent_augments = opponent_state.get("augments", [])
                    opponent_num_augments = len(opponent_augments)
                    opponent_num_traits = len(opponent_traits)

                streak = int(player_state.get("win_streak", 0)) - int(
                    player_state.get("loss_streak", 0)
                )
                rows.append(
                    {
                        "row_schema_version": 1,
                        "game_id": self.game_id,
                        "round": round_data["round"],
                        "player_id": pid,
                        "placement": placement_map.get(pid, 0),
                        "hp": player_state["hp"],
                        "gold": player_state["gold"],
                        "level": player_state["level"],
                        "streak": streak,
                        "board_count": player_state["board_count"],
                        "win_streak": player_state["win_streak"],
                        "loss_streak": player_state["loss_streak"],
                        "num_augments": len(player_state["augments"]),
                        "num_traits": len(player_state["traits"]),
                        "alive_count": round_data["alive_count"],
                        # Rich schema for model training
                        "units": units,
                        "traits": player_state["traits"],
                        "augments": player_state["augments"],
                        "opponent_units": opponent_units,
                        "opponent_traits": opponent_traits,
                        "opponent_hp": opponent_hp,
                        "opponent_gold": opponent_gold,
                        "opponent_level": opponent_level,
                        "opponent_win_streak": opponent_win_streak,
                        "opponent_loss_streak": opponent_loss_streak,
                        "opponent_streak": int(opponent_win_streak) - int(opponent_loss_streak),
                        "opponent_board_count": opponent_board_count,
                        "opponent_augments": opponent_augments,
                        "opponent_num_augments": opponent_num_augments,
                        "opponent_num_traits": opponent_num_traits,
                        "combat_result": matchup.get("combat_result"),
                        "damage_dealt": matchup.get("damage_dealt", 0.0),
                        "damage_taken": matchup.get("damage_taken", 0.0),
                        "combat_time": matchup.get("combat_time", 0.0),
                        "survivors": matchup.get("survivors", 0),
                        "is_ghost": matchup.get("is_ghost", False),
                        # Compact board representation
                        "board_names": [c["name"] for c in player_state["board"]],
                        "board_stars": [c["star"] for c in player_state["board"]],
                        "trait_names": list(player_state["traits"].keys()),
                        "trait_counts": list(player_state["traits"].values()),
                    }
                )
        return rows

    def get_analytics(self) -> Dict:
        """Extract balance analytics from this game.

        Returns counters that can be aggregated across many games.
        """
        analytics = {
            "comp_placements": [],  # (comp_signature, placement)
            "augment_placements": [],  # (augment_name, placement)
            "champion_placements": [],  # (champion_name, placement)
        }

        for p in self.placements:
            placement = p["placement"]

            # Comp signature: sorted list of champion names
            comp = tuple(sorted(c["name"] for c in p["board"]))
            analytics["comp_placements"].append((comp, placement))

            # Per-augment placement
            for aug in p["augments"]:
                analytics["augment_placements"].append((aug, placement))

            # Per-champion placement
            for ch in p["board"]:
                analytics["champion_placements"].append((ch["name"], placement))

        return analytics
