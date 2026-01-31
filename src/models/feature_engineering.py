"""
TFT Feature Engineering Module
Transforms raw match data into ML-ready features for placement prediction
"""

import pandas as pd
import numpy as np
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

from .role_rules import is_ad_role, is_ap_role


class FeatureEngineer:
    """Transforms raw TFT match data into ML-ready features"""

    def __init__(self, data_dir: str = None):
        """Initialize with path to data directory"""
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent
        self.data_dir = Path(data_dir)
        self.champions = {}
        self.traits = {}
        self._load_reference_data()

    def _load_reference_data(self):
        """Load champion and trait reference data from JSONL files"""
        # Load champions
        champ_file = self.data_dir / 'data' / 'game_data' / 'champions.jsonl'
        if champ_file.exists():
            with open(champ_file, 'r') as f:
                for line in f:
                    c = json.loads(line)
                    api_name = c.get('apiName', '')
                    # Extract clean name for matching
                    name = api_name.replace('TFT16_', '')
                    if not api_name.startswith('TFT16_'):
                        continue
                    self.champions[name] = {
                        'name': c.get('name', ''),
                        'cost': c.get('cost', 0),
                        'role': c.get('role', ''),
                        'traits': c.get('traits_pipe', '').split('|') if c.get('traits_pipe') else [],
                    }
                    # Also store with api_name key
                    self.champions[api_name] = self.champions[name]

        # Load traits
        traits_file = self.data_dir / 'data' / 'game_data' / 'traits.jsonl'
        if traits_file.exists():
            with open(traits_file, 'r') as f:
                for line in f:
                    t = json.loads(line)
                    api_name = t.get('apiName', '')
                    self.traits[api_name] = {
                        'name': t.get('name', ''),
                        'effects': t.get('effects', [])
                    }

    @staticmethod
    def parse_unit_string(unit_str: str) -> Tuple[Optional[str], Optional[int], List[str]]:
        """
        Parse unit string like: 'Viego_3*(Bloodthirster,TitansResolve,HextechGunblade)'
        Returns: (name, star_level, [items])
        """
        if not unit_str:
            return None, None, []

        # Pattern: Name_StarLevel*(items) or Name_StarLevel*()
        match = re.match(r'([A-Za-z0-9_]+)_(\d)\*\((.*?)\)', unit_str.strip())
        if match:
            name = match.group(1)
            star = int(match.group(2))
            items_str = match.group(3)
            items = [i.strip() for i in items_str.split(',') if i.strip()]
            return name, star, items
        return None, None, []

    @staticmethod
    def parse_traits_string(traits_str: str) -> Dict[str, int]:
        """
        Parse traits string like: 'Blacksmith:1 | KindredUnique:1 | Magus:1'
        Returns: dict of {trait_name: count}
        """
        if not traits_str or pd.isna(traits_str):
            return {}

        traits = {}
        for part in str(traits_str).split('|'):
            part = part.strip()
            if ':' in part:
                name, count = part.rsplit(':', 1)
                try:
                    traits[name.strip()] = int(count)
                except ValueError:
                    pass
        return traits

    def get_champion_role(self, name: str) -> str:
        """Get champion role (APCaster, ADCarry, etc.)"""
        champ = self.champions.get(name, {})
        return champ.get('role', 'Unknown')

    def get_champion_cost(self, name: str) -> int:
        """Get champion cost"""
        champ = self.champions.get(name, {})
        return champ.get('cost', 0)

    def is_ap_carry(self, role: str) -> bool:
        """Check if role is AP-based (Set 16 role rules)"""
        return is_ap_role(role)

    def is_ad_carry(self, role: str) -> bool:
        """Check if role is AD-based (Set 16 role rules)"""
        return is_ad_role(role)

    def extract_game_features(self, row: pd.Series) -> Dict:
        """Extract all features from a single game row"""
        features = {
            'placement': row['placement'],
            'top4': 1 if row['placement'] <= 4 else 0,
            'level': row['level'],
            'gold_left': row['gold_left'],
            'last_round': row['last_round'],
            'game_length_sec': row.get('game_length_sec', 0),
            'total_damage': row.get('total_damage_to_players', 0),
            'players_eliminated': row.get('players_eliminated', 0),
        }

        # Parse traits
        traits = self.parse_traits_string(row.get('traits_active', ''))

        # Trait features
        features['num_active_traits'] = len(traits)
        features['total_trait_levels'] = sum(traits.values())
        features['max_trait_level'] = max(traits.values()) if traits else 0

        # Binary trait features (whether active at any level)
        for trait_name in traits:
            if 'Unique' not in trait_name:  # Skip unique traits
                features[f'has_{trait_name}'] = 1
                features[f'trait_{trait_name}_level'] = traits[trait_name]

        # Parse units
        units = []
        units_str = row.get('final_board_units', '')
        if units_str and not pd.isna(units_str):
            for unit_part in str(units_str).split('|'):
                name, star, items = self.parse_unit_string(unit_part)
                if name:
                    units.append({
                        'name': name,
                        'star': star,
                        'items': items,
                        'cost': self.get_champion_cost(name),
                        'role': self.get_champion_role(name),
                        'item_count': len(items)
                    })

        # Unit count features
        features['num_units'] = len(units)
        features['total_items'] = sum(u['item_count'] for u in units)

        # Star level distribution
        features['avg_star_level'] = np.mean([u['star'] for u in units]) if units else 0
        features['num_3star'] = sum(1 for u in units if u['star'] == 3)
        features['num_2star'] = sum(1 for u in units if u['star'] == 2)
        features['num_1star'] = sum(1 for u in units if u['star'] == 1)

        # Cost distribution
        costs = [u['cost'] for u in units if u['cost'] > 0]
        features['avg_unit_cost'] = np.mean(costs) if costs else 0
        features['max_unit_cost'] = max(costs) if costs else 0
        features['total_board_cost'] = sum(costs)
        features['num_1cost'] = sum(1 for c in costs if c == 1)
        features['num_2cost'] = sum(1 for c in costs if c == 2)
        features['num_3cost'] = sum(1 for c in costs if c == 3)
        features['num_4cost'] = sum(1 for c in costs if c == 4)
        features['num_5cost'] = sum(1 for c in costs if c == 5)

        # Board value (cost * star level multiplier)
        features['board_value'] = sum(
            u['cost'] * (3 ** (u['star'] - 1)) for u in units if u['cost'] > 0
        )

        # Identify primary carry (unit with most items)
        if units:
            carry = max(units, key=lambda x: (x['item_count'], x['cost'], x['star']))
            features['carry_name'] = carry['name']
            features['carry_cost'] = carry['cost']
            features['carry_star'] = carry['star']
            features['carry_items'] = len(carry['items'])
            features['carry_role'] = carry['role']
            features['carry_is_ap'] = 1 if self.is_ap_carry(carry['role']) else 0
            features['carry_is_ad'] = 1 if self.is_ad_carry(carry['role']) else 0

            # Item breakdown on carry
            features['carry_item_list'] = carry['items']
        else:
            features['carry_name'] = None
            features['carry_cost'] = 0
            features['carry_star'] = 0
            features['carry_items'] = 0
            features['carry_role'] = 'Unknown'
            features['carry_is_ap'] = 0
            features['carry_is_ad'] = 0
            features['carry_item_list'] = []

        # Secondary carry (second most items)
        if len(units) > 1:
            sorted_units = sorted(units, key=lambda x: (x['item_count'], x['cost'], x['star']), reverse=True)
            secondary = sorted_units[1] if len(sorted_units) > 1 else None
            if secondary and secondary['item_count'] > 0:
                features['secondary_carry_name'] = secondary['name']
                features['secondary_carry_cost'] = secondary['cost']
                features['secondary_carry_items'] = secondary['item_count']
            else:
                features['secondary_carry_name'] = None
                features['secondary_carry_cost'] = 0
                features['secondary_carry_items'] = 0
        else:
            features['secondary_carry_name'] = None
            features['secondary_carry_cost'] = 0
            features['secondary_carry_items'] = 0

        return features

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform raw match dataframe into feature matrix"""
        all_features = []

        for idx, row in df.iterrows():
            try:
                features = self.extract_game_features(row)
                features['match_id'] = row.get('match_id', idx)
                all_features.append(features)
            except Exception as e:
                print(f"Error processing row {idx}: {e}")
                continue

        feature_df = pd.DataFrame(all_features)
        return feature_df

    def get_ml_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Get ML-ready feature matrix (X) and target (y)
        Drops non-numeric and categorical columns, returns only numeric features
        """
        feature_df = self.transform(df)

        # Columns to exclude from features
        exclude_cols = [
            'match_id', 'placement', 'top4',  # Target and ID
            'carry_name', 'carry_role', 'carry_item_list',  # Categorical
            'secondary_carry_name',  # Categorical
        ]

        # Columns that start with 'has_' or 'trait_' need to be included
        # but we'll fill missing trait columns with 0

        # Get all numeric columns
        numeric_cols = feature_df.select_dtypes(include=[np.number]).columns.tolist()
        feature_cols = [c for c in numeric_cols if c not in exclude_cols]

        X = feature_df[feature_cols].fillna(0)
        y = feature_df['top4']  # Binary: 1 if top4, 0 otherwise

        return X, y, feature_df

    def load_and_transform(self, csv_path: str = None) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        """Load CSV and transform to ML-ready features"""
        if csv_path is None:
            csv_path = self.data_dir / 'data' / 'personal' / 'tft_since_16_2_enhanced.csv'

        df = pd.read_csv(csv_path)
        return self.get_ml_features(df)


def main():
    """Test feature engineering"""
    print("Loading and transforming match data...")

    fe = FeatureEngineer()
    X, y, full_df = fe.load_and_transform()

    print(f"\nDataset shape: {X.shape}")
    print(f"Target distribution: {y.value_counts().to_dict()}")
    print(f"Top 4 rate: {y.mean()*100:.1f}%")

    print(f"\nFeature columns ({len(X.columns)}):")
    for col in sorted(X.columns):
        print(f"  - {col}")

    # Analyze carry type performance
    print("\n=== CARRY TYPE ANALYSIS ===")
    ap_games = full_df[full_df['carry_is_ap'] == 1]
    ad_games = full_df[full_df['carry_is_ad'] == 1]

    print(f"AP Carry games: {len(ap_games)}, Top 4 rate: {ap_games['top4'].mean()*100:.1f}%")
    print(f"AD Carry games: {len(ad_games)}, Top 4 rate: {ad_games['top4'].mean()*100:.1f}%")

    return X, y, full_df


if __name__ == "__main__":
    main()
