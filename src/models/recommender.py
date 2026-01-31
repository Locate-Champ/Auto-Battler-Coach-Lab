"""
TFT Board Recommender
Provides stage-aware recommendations based on:
- Meta early game comps
- Augment tier list
- Personal carry/trait performance
- Current board state analysis
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from .positioning_rules import get_baseline_rules, get_singed_positioning_status
from .role_rules import is_carry_role, is_frontline_role

class TFTRecommender:
    """Recommendation engine for TFT board building"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent
        self.data_dir = Path(data_dir)

        # Data stores
        self.early_comps = {}  # stage -> list of comps
        self.augment_tiers = {}  # augment_name -> tier info
        self.personal_carry_stats = {}  # carry -> performance
        self.personal_trait_stats = {}  # trait -> performance
        self.champions = {}  # champion reference data

        self._load_all_data()

    def _load_all_data(self):
        """Load all reference data"""
        self._load_early_game_comps()
        self._load_augment_tiers()
        self._load_personal_performance()
        self._load_champion_data()

    def _load_early_game_comps(self):
        """Load early game comp data by stage"""
        for stage_file in ['tft_set16_3_early_game_stage2_stage3.csv',
                           'tft_set16_3_early_game_stage4_stage5.csv']:
            path = self.data_dir / 'data' / 'personal' / stage_file
            if not path.exists():
                continue

            df = pd.read_csv(path)

            # Group by stage and comp rank
            for (stage, comp_rank), group in df.groupby(['Stage', 'CompRank']):
                if stage not in self.early_comps:
                    self.early_comps[stage] = []

                units = []
                for _, row in group.iterrows():
                    units.append({
                        'name': row['Unit'],
                        'star': row['StarLevel']
                    })

                comp_info = {
                    'rank': comp_rank,
                    'win_rate': group['WinRatePct'].iloc[0],
                    'avg_place': group['FinalPlace'].iloc[0],
                    'play_rate': group['PlayRate'].iloc[0],
                    'units': units
                }
                self.early_comps[stage].append(comp_info)

        # Sort by win rate within each stage
        for stage in self.early_comps:
            self.early_comps[stage].sort(key=lambda x: x['win_rate'], reverse=True)

    def _load_augment_tiers(self):
        """Load augment tier list"""
        path = self.data_dir / 'data' / 'meta' / 'metatft_augment_tierlist_16_3.csv'
        if not path.exists():
            return

        df = pd.read_csv(path)

        tier_scores = {'S': 5, 'A': 4, 'B': 3, 'C': 2, 'D': 1, 'F': 0}

        for _, row in df.iterrows():
            name = row['name']
            self.augment_tiers[name] = {
                'tier': row['tier'],
                'score': tier_scores.get(row['tier'], 2),
                'types': str(row.get('types', '')).split(', ') if pd.notna(row.get('types')) else [],
                'rarity': row.get('rarity', 'Unknown')
            }

    def _load_personal_performance(self):
        """Load personal carry and trait performance"""
        # Load carry performance
        carry_path = self.data_dir / 'data' / 'personal' / 'carry_performance_corrected.csv'
        if carry_path.exists():
            df = pd.read_csv(carry_path)
            for _, row in df.iterrows():
                self.personal_carry_stats[row.iloc[0]] = {
                    'games': row.get('games', row.get('Games', 0)),
                    'top4_rate': row.get('top4_rate', row.get('Top4Rate', 0)),
                    'avg_place': row.get('avg_place', row.get('AvgPlace', 4.5))
                }

        # Load trait performance
        trait_path = self.data_dir / 'data' / 'personal' / 'trait_performance_corrected.csv'
        if trait_path.exists():
            df = pd.read_csv(trait_path)
            for _, row in df.iterrows():
                self.personal_trait_stats[row.iloc[0]] = {
                    'games': row.get('games', row.get('Games', 0)),
                    'top4_rate': row.get('top4_rate', row.get('Top4Rate', 0)),
                    'avg_place': row.get('avg_place', row.get('AvgPlace', 4.5))
                }

    def _load_champion_data(self):
        """Load champion reference data"""
        champ_path = self.data_dir / 'data' / 'game_data' / 'champions.jsonl'
        if not champ_path.exists():
            return

        with open(champ_path, 'r') as f:
            for line in f:
                c = json.loads(line)
                api_name = c.get('apiName', '')
                if not api_name.startswith('TFT16_'):
                    continue
                name = c.get('name', '')
                self.champions[name] = {
                    'cost': c.get('cost', 0),
                    'role': c.get('role', ''),
                    'traits': c.get('traits_pipe', '').split('|') if c.get('traits_pipe') else []
                }

    def get_best_early_comps(self, stage: int, top_n: int = 5) -> List[Dict]:
        """Get top N early game comps for a stage"""
        if stage not in self.early_comps:
            return []
        return self.early_comps[stage][:top_n]

    def score_augment(self, augment_name: str) -> Dict:
        """Score an augment based on tier list"""
        if augment_name in self.augment_tiers:
            return self.augment_tiers[augment_name]

        # Fuzzy match - try to find partial match
        for name, info in self.augment_tiers.items():
            if augment_name.lower() in name.lower() or name.lower() in augment_name.lower():
                return info

        return {'tier': 'Unknown', 'score': 2, 'types': [], 'rarity': 'Unknown'}

    def get_augment_recommendations(self, rarity: str = None,
                                    prefer_types: List[str] = None,
                                    top_n: int = 10) -> List[Dict]:
        """Get recommended augments, optionally filtered"""
        augments = []

        for name, info in self.augment_tiers.items():
            if rarity and info['rarity'] != rarity:
                continue

            score = info['score']

            # Boost score if matches preferred types
            if prefer_types:
                matching_types = set(info['types']) & set(prefer_types)
                score += len(matching_types) * 0.5

            augments.append({
                'name': name,
                'tier': info['tier'],
                'score': score,
                'types': info['types'],
                'rarity': info['rarity']
            })

        augments.sort(key=lambda x: x['score'], reverse=True)
        return augments[:top_n]

    def get_augment_fit(self, traits: List[str],
                        trait_frequency: Optional[Dict[str, int]] = None,
                        total_comps: int = 0,
                        top_n: int = 3) -> List[Dict]:
        """Rank augments by trait fit and estimated enemy benefit."""
        if trait_frequency is None:
            trait_frequency = {}

        augment_pool = self.get_augment_recommendations(top_n=len(self.augment_tiers))
        if not augment_pool:
            return []

        normalized_traits = set(traits)
        total_comps = max(total_comps, 0)

        ranked = []
        for augment in augment_pool:
            matching_types = [t for t in augment['types'] if t in normalized_traits]
            match_count = len(matching_types)
            contested_count = sum(trait_frequency.get(t, 0) for t in matching_types)
            contested_share = contested_count / total_comps if total_comps else 0
            fit_score = augment['score'] + match_count * 0.6
            enemy_benefit = 'Low'
            if contested_share >= 0.35:
                enemy_benefit = 'High'
            elif contested_share >= 0.2:
                enemy_benefit = 'Medium'

            ranked.append({
                **augment,
                'matching_types': matching_types,
                'fit_score': fit_score,
                'enemy_benefit': enemy_benefit,
            })

        ranked.sort(key=lambda x: x['fit_score'], reverse=True)
        return ranked[:top_n]

    def analyze_board(self, units: List[Dict]) -> Dict:
        """
        Analyze current board state

        Args:
            units: List of {'name': str, 'star': int, 'items': List[str]}

        Returns:
            Analysis dict with gaps and recommendations
        """
        analysis = {
            'unit_count': len(units),
            'total_cost': 0,
            'avg_star': 0,
            'traits': defaultdict(int),
            'roles': defaultdict(int),
            'has_frontline': False,
            'has_carry': False,
            'has_cc': False,
            'item_count': 0,
            'gaps': [],
            'suggestions': [],
            'positioning_baseline': get_baseline_rules(),
            'singed_positioning': get_singed_positioning_status(),
        }

        if not units:
            analysis['gaps'].append("Empty board - need units!")
            return analysis

        stars = []
        itemized_units = []

        for unit in units:
            name = unit.get('name', '')
            star = unit.get('star', 1)
            items = unit.get('items', [])

            stars.append(star)
            analysis['item_count'] += len(items)

            if len(items) >= 2:
                itemized_units.append(name)

            # Get champion info
            champ_info = self.champions.get(name, {})
            cost = champ_info.get('cost', 0)
            role = champ_info.get('role', '')
            traits = champ_info.get('traits', [])

            analysis['total_cost'] += cost

            # Track roles
            if role:
                analysis['roles'][role] += 1
                if is_frontline_role(role):
                    analysis['has_frontline'] = True
                if is_carry_role(role):
                    analysis['has_carry'] = True

            # Track traits
            for trait in traits:
                analysis['traits'][trait] += 1

        analysis['avg_star'] = np.mean(stars) if stars else 0

        # Identify gaps
        if not analysis['has_frontline']:
            analysis['gaps'].append("Missing frontline (tanks/fighters)")
            analysis['suggestions'].append("Add: Shen, Sion, Illaoi, or Poppy")

        if not analysis['has_carry']:
            analysis['gaps'].append("Missing primary carry")
            analysis['suggestions'].append("Need a unit with 3 items to carry damage")

        if analysis['item_count'] < 6:
            analysis['gaps'].append(f"Low item count ({analysis['item_count']}/9 optimal)")

        if analysis['avg_star'] < 1.5:
            analysis['gaps'].append("Low star levels - need upgrades")

        # Check trait synergies
        active_traits = {t: c for t, c in analysis['traits'].items() if c >= 2}
        if len(active_traits) < 2:
            analysis['gaps'].append("Weak trait synergies")
            analysis['suggestions'].append("Focus on activating 2+ traits at higher levels")

        # Convert defaultdicts to regular dicts
        analysis['traits'] = dict(analysis['traits'])
        analysis['roles'] = dict(analysis['roles'])

        return analysis

    def recommend_for_board(self, current_units: List[Dict],
                           stage: int = 3,
                           available_gold: int = 50) -> Dict:
        """
        Get personalized recommendations based on current board

        Args:
            current_units: Current board state
            stage: Current game stage (2-6)
            available_gold: Gold available for rolling/leveling
        """
        recommendations = {
            'board_analysis': self.analyze_board(current_units),
            'meta_comps': [],
            'personal_carries': [],
            'transition_targets': [],
            'priority_actions': []
        }

        # Get relevant stage comps
        if stage in self.early_comps:
            recommendations['meta_comps'] = self.get_best_early_comps(stage, top_n=3)

        # Find current unit names
        current_names = {u.get('name', '').lower() for u in current_units}

        # Check personal carry performance
        for carry, stats in self.personal_carry_stats.items():
            if stats.get('games', 0) >= 3:
                top4_rate = stats.get('top4_rate', 0)
                if isinstance(top4_rate, str):
                    top4_rate = float(top4_rate.replace('%', '')) / 100
                elif top4_rate > 1:
                    top4_rate = top4_rate / 100

                if top4_rate >= 0.5:  # 50%+ top 4 rate
                    recommendations['personal_carries'].append({
                        'name': carry,
                        'top4_rate': f"{top4_rate*100:.0f}%",
                        'games': stats.get('games', 0),
                        'on_board': carry.lower() in current_names
                    })

        # Sort personal carries by top4 rate
        recommendations['personal_carries'].sort(
            key=lambda x: float(x['top4_rate'].replace('%', '')),
            reverse=True
        )

        # Generate priority actions
        analysis = recommendations['board_analysis']

        if analysis['gaps']:
            for gap in analysis['gaps'][:3]:
                recommendations['priority_actions'].append(f"FIX: {gap}")

        if stage <= 3 and available_gold >= 10:
            recommendations['priority_actions'].append("Consider: Save for level 6 at stage 3-2")
        elif stage == 4 and available_gold >= 30:
            recommendations['priority_actions'].append("Consider: Roll for upgrades or push level 7")

        # Suggest transition based on meta comps
        if recommendations['meta_comps']:
            best_comp = recommendations['meta_comps'][0]
            comp_units = {u['name'].lower() for u in best_comp['units']}
            overlap = current_names & comp_units

            if len(overlap) >= 2:
                missing = comp_units - current_names
                if missing:
                    recommendations['transition_targets'].append({
                        'comp_rank': best_comp['rank'],
                        'win_rate': f"{best_comp['win_rate']}%",
                        'you_have': list(overlap),
                        'you_need': list(missing)[:4]
                    })

        return recommendations

    def format_recommendations(self, recs: Dict) -> str:
        """Format recommendations as readable text"""
        lines = []
        lines.append("=" * 60)
        lines.append("TFT BOARD RECOMMENDATIONS")
        lines.append("=" * 60)

        # Board analysis
        analysis = recs['board_analysis']
        lines.append(f"\nBOARD STATE: {analysis['unit_count']} units, "
                    f"{analysis['item_count']} items, "
                    f"avg {analysis['avg_star']:.1f}* star level")

        if analysis['traits']:
            trait_str = ", ".join(f"{t}:{c}" for t, c in
                                 sorted(analysis['traits'].items(), key=lambda x: -x[1])[:5])
            lines.append(f"Active traits: {trait_str}")

        # Positioning baseline
        if analysis.get('positioning_baseline'):
            lines.append("\nPOSITIONING BASELINE (Set 16):")
            for rule in analysis['positioning_baseline'][:6]:
                lines.append(f"  - {rule}")

        singed_status = analysis.get('singed_positioning', {})
        if singed_status:
            lines.append("\nSINGED POSITIONING STATUS:")
            lines.append(f"  - {singed_status.get('status', 'unknown')}")
            reason = singed_status.get('reason')
            if reason:
                lines.append(f"    {reason}")

        # Gaps
        if analysis['gaps']:
            lines.append("\nGAPS TO ADDRESS:")
            for gap in analysis['gaps']:
                lines.append(f"  ! {gap}")

        # Personal best carries
        if recs['personal_carries']:
            lines.append("\nYOUR BEST CARRIES (based on your history):")
            for carry in recs['personal_carries'][:5]:
                status = "[ON BOARD]" if carry['on_board'] else ""
                lines.append(f"  - {carry['name']}: {carry['top4_rate']} top4 "
                           f"({carry['games']} games) {status}")

        # Meta comps
        if recs['meta_comps']:
            lines.append(f"\nMETA COMPS FOR THIS STAGE:")
            for comp in recs['meta_comps'][:3]:
                unit_names = [f"{u['name']}_{u['star']}*" for u in comp['units']]
                lines.append(f"  #{comp['rank']}: {comp['win_rate']}% WR, "
                           f"avg {comp['avg_place']:.1f} place")
                lines.append(f"      Units: {', '.join(unit_names)}")

        # Transition targets
        if recs['transition_targets']:
            lines.append("\nTRANSITION OPPORTUNITY:")
            for target in recs['transition_targets']:
                lines.append(f"  Comp #{target['comp_rank']} ({target['win_rate']} WR)")
                lines.append(f"    You have: {', '.join(target['you_have'])}")
                lines.append(f"    You need: {', '.join(target['you_need'])}")

        # Priority actions
        if recs['priority_actions']:
            lines.append("\nPRIORITY ACTIONS:")
            for action in recs['priority_actions']:
                lines.append(f"  >> {action}")

        return '\n'.join(lines)


def main():
    """Demo the recommender"""
    print("Initializing TFT Recommender...")
    rec = TFTRecommender()

    # Show what data we have
    print(f"\nLoaded data:")
    print(f"  - Early comps for stages: {list(rec.early_comps.keys())}")
    print(f"  - Augments in tier list: {len(rec.augment_tiers)}")
    print(f"  - Personal carry stats: {len(rec.personal_carry_stats)}")
    print(f"  - Personal trait stats: {len(rec.personal_trait_stats)}")
    print(f"  - Champion data: {len(rec.champions)}")

    # Example: Get best stage 2 comps
    print("\n" + "=" * 60)
    print("BEST STAGE 2 COMPS (meta)")
    print("=" * 60)
    for comp in rec.get_best_early_comps(2, top_n=5):
        units = [f"{u['name']}_{u['star']}*" for u in comp['units']]
        print(f"  #{comp['rank']}: {comp['win_rate']}% WR -> {', '.join(units)}")

    # Example: Get best stage 4 comps
    print("\n" + "=" * 60)
    print("BEST STAGE 4 COMPS (meta)")
    print("=" * 60)
    for comp in rec.get_best_early_comps(4, top_n=5):
        units = [f"{u['name']}_{u['star']}*" for u in comp['units']]
        print(f"  #{comp['rank']}: {comp['win_rate']}% WR -> {', '.join(units)}")

    # Example: Top augments
    print("\n" + "=" * 60)
    print("TOP S-TIER AUGMENTS")
    print("=" * 60)
    for aug in rec.get_augment_recommendations(top_n=10):
        if aug['tier'] == 'S':
            print(f"  {aug['name']} ({aug['rarity']}): {', '.join(aug['types']) or 'General'}")

    # Example: Analyze a sample board
    print("\n" + "=" * 60)
    print("EXAMPLE BOARD ANALYSIS")
    print("=" * 60)
    sample_board = [
        {'name': 'Viego', 'star': 2, 'items': ['Bloodthirster', 'Titans Resolve']},
        {'name': 'Shen', 'star': 2, 'items': ['Warmogs']},
        {'name': 'Twisted Fate', 'star': 1, 'items': []},
        {'name': 'Yorick', 'star': 1, 'items': []},
    ]

    recs = rec.recommend_for_board(sample_board, stage=3, available_gold=30)
    print(rec.format_recommendations(recs))


if __name__ == "__main__":
    main()
