"""Data collector for TFT game simulations.

Hooks into TFTGame to capture per-round state snapshots, combat results,
and final placements for ML training data and balance analytics.
"""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .game import TFTGame


class GameCollector:
    """Collects ML training data + balance analytics from a single game."""

    def __init__(self, game_id: int):
        self.game_id = game_id
        self.rounds: List[Dict] = []
        self.placements: List[Dict] = []

    def on_round_end(self, game: 'TFTGame', round_num: int,
                     combat_results: List[Dict]):
        """Called after each PvP round.

        Args:
            game: The TFTGame instance.
            round_num: Current round number.
            combat_results: List of combat result dicts from this round.
        """
        round_data = {
            'round': round_num,
            'alive_count': len(game.alive_players),
            'players': [],
            'combats': combat_results,
        }

        for player in game.players:
            if not player.alive:
                continue
            # Compact state snapshot for ML training
            board_champs = []
            for (r, c), ch in player.board.items():
                board_champs.append({
                    'name': ch.name,
                    'star': ch.star_level,
                    'items': ch.items[:],
                    'pos': [r, c],
                })

            round_data['players'].append({
                'id': player.player_id,
                'hp': player.hp,
                'gold': player.gold,
                'level': player.level,
                'board': board_champs,
                'board_count': player.board_count,
                'traits': player.get_active_traits(),
                'augments': game.player_augments.get(player.player_id, []),
                'win_streak': player.win_streak,
                'loss_streak': player.loss_streak,
            })

        self.rounds.append(round_data)

    def on_game_end(self, game: 'TFTGame'):
        """Called when the game finishes."""
        for player_id, placement in game.placements:
            player = game.players[player_id]
            # Final board composition
            board_champs = []
            for (r, c), ch in player.board.items():
                board_champs.append({
                    'name': ch.name,
                    'star': ch.star_level,
                    'items': ch.items[:],
                })

            self.placements.append({
                'player_id': player_id,
                'placement': placement,
                'level': player.level,
                'hp': player.hp,
                'board': board_champs,
                'traits': player.get_active_traits(),
                'augments': game.player_augments.get(player_id, []),
            })

    def to_dict(self) -> Dict:
        """Serialize collected data to a dict."""
        return {
            'game_id': self.game_id,
            'num_rounds': len(self.rounds),
            'placements': self.placements,
            'rounds': self.rounds,
        }

    def get_training_rows(self) -> List[Dict]:
        """Extract flat ML training rows (one per player per round).

        Each row contains the player's state at round N and their
        final placement as the label. This is the format needed for
        supervised learning (predict placement from board state).
        """
        # Build placement lookup
        placement_map = {p['player_id']: p['placement'] for p in self.placements}

        rows = []
        for round_data in self.rounds:
            for player_state in round_data['players']:
                pid = player_state['id']
                rows.append({
                    'game_id': self.game_id,
                    'round': round_data['round'],
                    'player_id': pid,
                    'placement': placement_map.get(pid, 0),
                    'hp': player_state['hp'],
                    'gold': player_state['gold'],
                    'level': player_state['level'],
                    'board_count': player_state['board_count'],
                    'win_streak': player_state['win_streak'],
                    'loss_streak': player_state['loss_streak'],
                    'num_augments': len(player_state['augments']),
                    'num_traits': len(player_state['traits']),
                    'alive_count': round_data['alive_count'],
                    # Compact board representation
                    'board_names': [c['name'] for c in player_state['board']],
                    'board_stars': [c['star'] for c in player_state['board']],
                    'trait_names': list(player_state['traits'].keys()),
                    'trait_counts': list(player_state['traits'].values()),
                    'augments': player_state['augments'],
                })
        return rows

    def get_analytics(self) -> Dict:
        """Extract balance analytics from this game.

        Returns counters that can be aggregated across many games.
        """
        analytics = {
            'comp_placements': [],  # (comp_signature, placement)
            'augment_placements': [],  # (augment_name, placement)
            'champion_placements': [],  # (champion_name, placement)
        }

        for p in self.placements:
            placement = p['placement']

            # Comp signature: sorted list of champion names
            comp = tuple(sorted(c['name'] for c in p['board']))
            analytics['comp_placements'].append((comp, placement))

            # Per-augment placement
            for aug in p['augments']:
                analytics['augment_placements'].append((aug, placement))

            # Per-champion placement
            for ch in p['board']:
                analytics['champion_placements'].append((ch['name'], placement))

        return analytics
