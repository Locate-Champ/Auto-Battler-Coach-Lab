# TFT Coach ML Pipeline — Codex Implementation Instructions

> Feed this entire document as context to Codex / Claude Code / any coding LLM.
> Last updated: 2026-02-16
> Repo: `e:\VS Code\tft-coach-234`

---

## CONTEXT BLOCK (Read First — Do Not Skip)

### What This Project Is

A Teamfight Tactics (TFT) coaching application that uses machine learning to predict combat outcomes and recommend optimal board states. The system has three layers:

1. **Combat Simulator** (DONE) — A deterministic, tick-based (30 FPS) full-game simulator in Python that generates synthetic training data. Benchmarked at 2,717 full 8-player games/hour. Determinism verified. 106 champions, 283 augments, 134 items, 53 traits implemented.

2. **ML Prediction Models** (ACTIVE) — XGBoost + Transformer pipelines are implemented in `models/` and trained on simulator output.

3. **Coaching Interface** (LATER) — React frontend consuming model predictions. Not in scope for this document.

### Current Codebase Layout

Status note: the core `models/` pipeline files referenced in this document already exist in this repo. Sections that say "Create `<file>`" should be interpreted as "update/extend `<file>` unless explicitly building a new module."

```
tft-coach-234/
├── simulator/
│   ├── cloud_runner.py          # 693 lines — Production batch runner (entry point)
│   ├── benchmark.py             # Throughput + determinism tests
│   ├── game/
│   │   ├── game.py              # 718 lines — Full 8-player game loop
│   │   ├── player.py            # 644 lines — Player state, economy, leveling
│   │   ├── actions.py           # 530 lines — Shop, level, position, item actions
│   │   ├── constants.py         # 271 lines — All game constants
│   │   └── collector.py         # 162 lines — Training row snapshots
│   ├── core/
│   │   ├── combat_engine.py     # 4690 lines — Tick-based combat simulation
│   │   ├── champion_abilities.py# 5124 lines — 103 ability handlers
│   │   └── item_effects.py      # 1245 lines — Item hooks (on_hit, passive, etc.)
│   ├── data/
│   │   ├── combat_data.json     # Champion stats (106 entries)
│   │   ├── traits.json          # 53 trait definitions
│   │   └── validate_reference_data.py
│   └── config.py                # 268 lines — Legacy RL config (observation_size=10432)
├── data/api/processed/
│   └── augments_set16.json      # 283 augments
├── models/                      # ACTIVE — Feature engineering, loaders, XGBoost, transformer, eval
├── training_data/               # Generated datasets from simulator (Parquet/JSONL chunks)
├── scripts/
│   ├── generate_data.py         # Calls cloud_runner for batch gen
│   ├── train.py                 # Model training entry point
│   └── validate.py              # Accuracy validation vs real matches
└── requirements.txt
```

### How to Run the Simulator

```bash
# Generate 1000 full 8-player games, output to parquet
python -m simulator.cloud_runner --games 1000 --workers 11 --output results/batch

# Quick benchmark
python -m simulator.benchmark
# Expected: ~177 sims/sec (1v1), ~63 sims/sec (4v4), ~2717 games/hour (full 8-player)
```

### Simulator Output Schema

The collector produces one row per alive player per PvP round with this structure:

```python
# Each training row (from collector.py)
{
    "game_id": int,
    "round": int,
    "player_id": int,
    "level": int,               # 1-10
    "hp": int,                  # 0-100
    "gold": int,
    "streak": int,
    "units": [                  # Up to 14 unit slots (level + bench overflow)
        {
            "champion_id": str,     # e.g. "TFT16_Fiddlesticks"
            "star_level": int,      # 1-3
            "items": [str, ...],    # Up to 3 item apiNames
            "position": int,        # 0-27 hex index (4 rows x 7 cols)
        }
    ],
    "traits": {str: int},       # Active trait -> breakpoint level
    "augments": [str, str, str], # Up to 3 augment apiNames
    "opponent_units": [...],     # Same structure as units
    "opponent_traits": {...},
    "combat_result": int,        # 0=loss, 1=win, 2=draw
    "damage_dealt": float,
    "damage_taken": float,
    "placement": int             # Final placement 1-8 (only on elimination/win)
}
```

### Key Game Constants

```python
TICK_RATE = 30                    # 30 ticks/second, 0.033s per tick
MAX_COMBAT_TIME = 60.0            # seconds
BOARD_SIZE = (4, 7)               # 28 hexes
MAX_UNITS_ON_BOARD = 10           # at level 10
BENCH_SIZE = 9
MAX_ITEMS_PER_UNIT = 3
STARTING_HP = 100
STAR_SCALING_HP = [1.0, 1.8, 3.24]
STAR_SCALING_AD = [1.0, 1.5, 2.25]
ATTACK_SPEED_CAP = 5.0
MANA_ON_ATTACK = 10
MANA_ON_DAMAGE_CAP = 42.5

# Champion pool by cost tier
POOL_SIZES = {1: 30, 2: 25, 3: 18, 4: 10, 5: 9, 7: 9}
CHAMPION_COUNTS = {1: 14, 2: 19, 3: 18, 4: 25, 5: 18, 7: 6}  # 100 rollable total
```

### Owner's Personal Performance Data (163 games)

This is critical context — the coaching system weights recommendations by personal performance, not generic meta.

```
S-TIER carries (100% top 4): Fiddlesticks (avg 1.75), Ornn (avg 2.14), Sett (avg 2.67)
A-TIER carries (75-80% top 4): Zilean, Thresh, Azir
F-TIER carries (0% top 4): Miss Fortune, Bel'Veth, Jinx, Kai'Sa

Best items: Protector's Vow (100% top4), Edge of Night, Blue Buff, Spirit Visage
Worst items: Warmog's (0% top4), Infinity Edge (20%), Giant Slayer (25%)

Pattern: Late-game AP/utility >>> AD carries for this player
```

### Code Style Requirements

- Python 3.10+
- Type hints required on all function signatures
- Docstrings on all public methods
- Use `dataclasses` or `pydantic` for data structures
- Use `multiprocessing` for parallelism (not asyncio — CPU-bound workload)
- PyTorch for all neural network code (not TensorFlow)
- Target CUDA first, fallback MPS, fallback CPU

---

## PHASE 1: XGBoost/LightGBM Baseline (Build This First)

### Goal

Get a working end-to-end prediction pipeline in <500 lines. This validates that the problem is learnable, establishes accuracy baselines, and identifies which features carry signal before investing in expensive neural architectures.

### Target Metrics

- Fight outcome prediction (win/loss): >65% accuracy
- Top4 vs Bot4 classification: >70% accuracy
- Placement prediction (1-8): <1.5 MAE

### Step 1.1: Feature Engineering Module

Create `models/feature_engineering.py`.

This is the most important file in the entire ML pipeline. XGBoost accuracy depends almost entirely on feature quality.

```python
"""
Feature engineering for TFT board states.
Transforms raw simulator output into ML-ready feature vectors.

Input: A single training row from the simulator collector
Output: A flat numpy array of engineered features

IMPORTANT: All features must be numeric. Categorical variables must be encoded.
"""

from dataclasses import dataclass
import numpy as np
from typing import Dict, List, Optional

@dataclass
class FeatureConfig:
    """Controls which feature groups are active. Use for ablation studies."""
    use_composition: bool = True
    use_economy: bool = True
    use_traits: bool = True
    use_items: bool = True
    use_augments: bool = True
    use_matchup: bool = True       # Cross-team features
    use_positioning: bool = False   # Start without — add later
    use_personal_weights: bool = True  # Owner's performance data


class TFTFeatureEngineer:
    """
    Transforms raw board state into engineered feature vector.
    
    Feature groups (implement all of these):
    
    1. COMPOSITION FEATURES (~20 features)
       - total_team_cost: sum of champion costs on board
       - avg_star_level: mean star level
       - num_3_stars: count of 3-star units
       - num_units_by_cost: count of 1/2/3/4/5/7-cost units (6 features)
       - total_hp_pool: sum of base HP * star scaling for all units
       - total_ad_pool: sum of base AD * star scaling
       - total_ap_pool: sum of AP from items/traits
       - avg_attack_speed: mean effective attack speed
       - avg_armor: mean armor
       - avg_mr: mean MR
       - team_dps_estimate: rough DPS = sum(AD * AS) for all units
       - frontline_tankiness: sum HP of front 2 rows
       - backline_damage: sum AD/AP of back 2 rows
    
    2. ECONOMY FEATURES (~8 features)
       - level: player level (1-10)
       - hp: current HP (0-100)
       - hp_percentage: hp / 100
       - gold: current gold
       - streak: win/loss streak value
       - round: current round number
       - stage: derived from round (round // 7 + 1 approximately)
       - interest_gold: gold // 10, capped at 5
    
    3. TRAIT FEATURES (~53+ features)
       For EACH of the 53 traits:
       - trait_X_count: number of units with this trait
       - trait_X_active: 1 if breakpoint is met, 0 otherwise
       - trait_X_tier: which breakpoint tier (0, 1, 2, 3...)
       NOTE: Load trait breakpoints from simulator/data/traits.json
    
    4. ITEM FEATURES (~30 features)
       - total_completed_items: count of completed (non-component) items
       - total_components: count of loose components
       - has_qss: binary — any unit has Quicksilver
       - has_guardbreaker: binary
       - has_blue_buff: binary
       - has_shojin: binary
       - has_morello: binary
       - has_ionic_spark: binary
       - carry_item_count: items on most-itemized unit
       - carry_has_bis: 1 if carry has 3 completed items
       - item_type_counts: count of offensive/defensive/utility items
       - total_item_ad: sum of AD from all items
       - total_item_ap: sum of AP from all items
       - total_item_hp: sum of HP from all items
       - total_item_as: sum of attack speed from all items
       - total_item_armor: sum of armor from all items
       - total_item_mr: sum of MR from all items
    
    5. AUGMENT FEATURES (~10 features)
       - augment_tier_sum: sum of augment tiers (silver=1, gold=2, prismatic=3)
       - has_econ_augment: binary (Rich get Richer, Hedge Fund, etc.)
       - has_combat_augment: binary
       - has_trait_augment: binary
       - augment_X_encoded: one-hot or embedding index for each of 3 augment slots
       NOTE: Augment tier can be inferred from augment name patterns or the
       augments_set16.json data
    
    6. MATCHUP FEATURES (~15 features)
       These compare YOUR board vs OPPONENT board:
       - cost_advantage: your total_cost - opponent total_cost
       - star_advantage: your avg_stars - opponent avg_stars
       - hp_advantage: your hp - opponent hp
       - item_advantage: your total_items - opponent total_items
       - frontline_hp_ratio: your frontline HP / opponent frontline HP
       - backline_dps_ratio: your backline DPS / opponent backline DPS
       - armor_vs_physical: your avg armor vs opponent physical DPS share
       - mr_vs_magic: your avg MR vs opponent magic DPS share
       - has_qss_vs_cc: your QSS count vs opponent CC-heavy unit count
       - trait_overlap: number of shared active traits (contested = bad)
       - your_carry_cost - opponent_carry_cost
       - your_carry_stars - opponent_carry_stars
    
    7. PERSONAL PERFORMANCE WEIGHTS (optional, for personalized model)
       - carry_personal_winrate: owner's historical top4 rate with their main carry
       - carry_personal_avg_place: owner's historical avg placement
       - item_personal_score: weighted sum of item performance from personal data
       NOTE: Load from performance_reference.json
    """
    
    def __init__(self, config: FeatureConfig = None):
        self.config = config or FeatureConfig()
        # Load reference data here:
        # - traits.json for breakpoints
        # - combat_data.json for champion base stats
        # - items data for item stat lookups
        # - performance_reference.json for personal weights
        # - augments_set16.json for augment metadata
        pass
    
    def transform(self, row: dict) -> np.ndarray:
        """Transform a single collector row into feature vector."""
        features = []
        if self.config.use_composition:
            features.extend(self._composition_features(row))
        if self.config.use_economy:
            features.extend(self._economy_features(row))
        if self.config.use_traits:
            features.extend(self._trait_features(row))
        if self.config.use_items:
            features.extend(self._item_features(row))
        if self.config.use_augments:
            features.extend(self._augment_features(row))
        if self.config.use_matchup:
            features.extend(self._matchup_features(row))
        if self.config.use_personal_weights:
            features.extend(self._personal_features(row))
        return np.array(features, dtype=np.float32)
    
    def feature_names(self) -> List[str]:
        """Return ordered list of feature names matching transform() output.
        CRITICAL for XGBoost feature importance analysis."""
        pass
    
    # Implement each _*_features method returning List[float]
```

### Step 1.2: Data Loading Pipeline

Create `models/data_loader.py`.

```python
"""
Load parquet/JSONL training data from simulator output and convert to
feature matrices for XGBoost.

Usage:
    loader = DataLoader("results/batch")
    X_train, X_test, y_train, y_test = loader.load_fight_prediction_data(test_size=0.2)
"""

import pyarrow.parquet as pq
import json
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from typing import Tuple

class DataLoader:
    """
    Reads simulator output chunks (parquet or JSONL) and produces
    ML-ready feature matrices.
    
    Implement these methods:
    
    1. load_raw(data_dir: str) -> List[dict]
       - Scan for .parquet and .jsonl files in data_dir
       - Read and concatenate all rows
       - Return list of raw collector row dicts
    
    2. load_fight_prediction_data(test_size=0.2, seed=42) -> Tuple
       - Target: combat_result (0=loss, 1=win) — drop draws or make 3-class
       - Returns: X_train, X_test, y_train, y_test as numpy arrays
       - Apply FeatureEngineer.transform() to each row
    
    3. load_placement_prediction_data(test_size=0.2, seed=42) -> Tuple
       - Target: final placement (1-8)
       - Only use rows where placement is set (elimination + winner)
       - Returns: X_train, X_test, y_train, y_test
    
    4. load_top4_classification_data(test_size=0.2, seed=42) -> Tuple
       - Target: binary (placement <= 4 = 1, else 0)
       - Same filtering as placement
    
    Print dataset stats on load:
       - Total rows, train/test split sizes
       - Class balance (win/loss ratio, top4/bot4 ratio)
       - Feature count
    """
    pass
```

### Step 1.3: XGBoost Training Script

Create `models/train_xgboost.py`.

```python
"""
Train XGBoost models for TFT prediction tasks.

Usage:
    python -m models.train_xgboost --data results/batch --task fight --output models/checkpoints/

Tasks:
    fight     — Binary: predict combat win/loss
    top4      — Binary: predict top 4 vs bottom 4 placement
    placement — Regression: predict final placement 1-8

IMPORTANT: After training, print:
    1. Test accuracy / AUC-ROC / MAE (depending on task)
    2. Top 20 feature importances with names
    3. Confusion matrix for classification tasks
    4. Save model to --output as .json (XGBoost native format)
    5. Save feature importance chart as PNG
"""

import xgboost as xgb
from sklearn.metrics import (
    accuracy_score, roc_auc_score, confusion_matrix,
    mean_absolute_error, classification_report
)
import matplotlib.pyplot as plt
import argparse

# Hyperparameters to start with (tune later):
FIGHT_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "max_depth": 8,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_alpha": 0.1,       # L1 regularization
    "reg_lambda": 1.0,      # L2 regularization
    "tree_method": "hist",   # Fast histogram-based
    "device": "cuda",        # Use GPU if available, fallback to cpu
    "early_stopping_rounds": 50,
}

PLACEMENT_PARAMS = {
    "objective": "reg:squarederror",
    "eval_metric": "mae",
    "max_depth": 8,
    "learning_rate": 0.05,
    "n_estimators": 500,
    # ... same regularization as above
}

# After training, ALWAYS run feature importance analysis:
# - Plot top 20 features by gain
# - Print them to console
# - This tells us which features matter most for the transformer architecture later

# Also run ablation study:
# - Train with each feature group disabled one at a time
# - Print accuracy delta for each group
# - This tells us which feature engineering decisions matter
```

### Step 1.4: Generate Training Data

Before training, generate data:

```bash
# Generate 10,000 games for the baseline (~3.7 hours on 12 cores)
python -m simulator.cloud_runner --games 10000 --workers 11 --output training_data/baseline_10k --agent-profile mixed

# Generate 1,000 games for quick iteration (~22 minutes)
python -m simulator.cloud_runner --games 1000 --workers 11 --output training_data/quick_1k --agent-profile mixed

# Use 'mixed' agent profile for diversity: random/econ/slam = 50/30/20
```

### Step 1.5: Evaluation & Reporting

Create `models/evaluate.py`.

```python
"""
Comprehensive model evaluation with statistical rigor.

For EVERY model trained, compute and print:

1. Primary metrics (task-dependent):
   - Fight: Accuracy, AUC-ROC, precision, recall, F1
   - Top4: Same as fight
   - Placement: MAE, RMSE, Spearman rank correlation

2. Calibration analysis:
   - For classifiers: calibration curve (predicted prob vs actual frequency)
   - If model says "70% win", it should actually win ~70% of the time
   - Use sklearn.calibration.calibration_curve

3. Wilson confidence intervals:
   - For all rate-based metrics, compute 95% Wilson CI
   - Formula: (p + z²/2n ± z√(p(1-p)/n + z²/4n²)) / (1 + z²/n)
   - Where z = 1.96 for 95% CI

4. Feature importance ranking:
   - XGBoost: built-in gain/cover/weight importance
   - Rank top 20, print table
   - Save as JSON for use in later phases

5. Mutual information analysis:
   - Compute I(feature; target) for each feature
   - This is MODEL-INDEPENDENT feature importance
   - sklearn.feature_selection.mutual_info_classif
   - Compare with XGBoost feature importance — discrepancies reveal
     features the model isn't using well

6. Cross-validation:
   - 5-fold stratified CV for all classification tasks
   - Report mean ± std for each metric

Save all results to models/checkpoints/evaluation_report.json
"""
```

---

## PHASE 2: Transformer with Cross-Attention (Main Architecture)

### Goal

Build the S-tier architecture identified in project analysis. This is the endgame model — self-attention learns which units matter, cross-attention learns matchup interactions, positional encoding handles board positioning.

### Target Metrics

- Fight outcome prediction: >80% accuracy
- Top4 classification: >82% accuracy
- Placement MAE: <1.2

### Data Requirements

Train on ≥1M simulated games (≈15 hours on 12 cores). More is better — accuracy scales logarithmically with data.

```bash
# Generate 1M games in chunks (use checkpoint/resume)
python -m simulator.cloud_runner --games 1000000 --workers 11 --output training_data/1M --agent-profile ladder --chunk-size 1000
```

### Step 2.1: Unit Embedding Module

Create `models/embeddings.py`.

```python
"""
Learned embeddings for TFT game entities.

This module converts raw game state into dense vector representations
that the transformer can process.

ARCHITECTURE DECISIONS (implement exactly as specified):

1. CHAMPION EMBEDDING
   - Vocabulary: 109 (106 combat champions + 2 special tokens + 1 padding)
     - Index 0: PAD (empty unit slot)
     - Index 1: UNK (unknown champion)
     - Index 2-107: The 106 champions from combat_data.json
   - Embedding dimension: 64
   - nn.Embedding(109, 64, padding_idx=0)

2. ITEM EMBEDDING
   - Vocabulary: 152 (from model_lookups item_len)
   - Each unit has up to 3 item slots
   - Embedding dimension: 32
   - Aggregate per-unit: sum or mean of 3 item embeddings
   - nn.Embedding(152, 32, padding_idx=0)
   - Project to 64 dim: nn.Linear(32, 64)

3. POSITION ENCODING (hex grid)
   - 28 hex positions on a 4x7 board
   - Use LEARNED positional embeddings (not sinusoidal)
   - nn.Embedding(29, 64)  # 28 positions + 1 for bench/unknown
   - Hex coordinate features as auxiliary input:
     - row (0-3), col (0-6), normalized_row, normalized_col
     - is_frontline (row 0-1), is_backline (row 2-3)
     - hex_ring (distance from center)

4. STAR LEVEL ENCODING
   - 3 levels: 1, 2, 3
   - nn.Embedding(4, 16, padding_idx=0)  # 0=pad, 1-3=stars
   - Project: nn.Linear(16, 64)

5. COST TIER ENCODING
   - 6 cost tiers: 1, 2, 3, 4, 5, 7
   - nn.Embedding(8, 16, padding_idx=0)  # 0=pad, 1-7=cost
   - Project: nn.Linear(16, 64)

6. UNIT ENCODER (combines all per-unit features)
   Input: champion_embed(64) + item_embed(64) + position_embed(64)
          + star_embed(64) + cost_embed(64) = 320
   Output: nn.Linear(320, 128) -> LayerNorm -> ReLU -> nn.Linear(128, 64)
   
   This produces a single 64-dim vector per unit.

7. TRAIT ENCODING
   - 53 traits with activation tiers
   - Input: 53-dim vector of trait activation levels (0, 1, 2, 3, 4)
   - nn.Linear(53, 64) -> LayerNorm -> ReLU

8. AUGMENT ENCODING
   - Vocabulary: 374 (from augment_encodings)
   - 3 augment slots per player
   - nn.Embedding(375, 32, padding_idx=0)
   - Aggregate: sum of 3 augment embeddings
   - Project: nn.Linear(32, 64)

9. GAME STATE ENCODING
   - Scalar features: level, hp, gold, streak, round, stage
   - nn.Linear(6, 64) -> LayerNorm -> ReLU
"""

import torch
import torch.nn as nn

class UnitEmbedding(nn.Module):
    """Embeds a single TFT unit into a 64-dim vector."""
    pass

class BoardEncoder(nn.Module):
    """
    Encodes an entire board state (up to 14 units + board-level features)
    into a sequence of unit embeddings + global context vector.
    
    Output shape: (batch, max_units, embed_dim) + (batch, embed_dim) for global
    Also output a padding mask: (batch, max_units) boolean
    """
    pass
```

### Step 2.2: Transformer Architecture

Create `models/transformer.py`.

```python
"""
TFTTransformerV2: Cross-attention transformer for TFT combat prediction.

ARCHITECTURE (implement exactly):

Input Processing:
  Player board  → BoardEncoder → (batch, 14, 64) unit sequence + (batch, 64) global
  Opponent board → BoardEncoder → (batch, 14, 64) unit sequence + (batch, 64) global
  (BoardEncoder weights are SHARED — Siamese style)

Self-Attention (per team):
  - 2 layers of TransformerEncoderLayer
  - 4 attention heads
  - dim_feedforward = 256
  - dropout = 0.1
  - Learns: which units on YOUR board interact with each other
  - Example: "Fiddlesticks + Blue Buff matters more than Fiddlesticks alone"
  - Apply padding mask so empty slots don't attend

Cross-Attention (between teams):
  - 1 layer of MultiheadAttention
  - Query: your units, Key/Value: opponent units
  - 4 heads, embed_dim = 64
  - Learns: matchup-specific interactions
  - Example: "Your Fiddlesticks vs their QSS Jinx = bad matchup"
  - Apply padding mask for both sides

Aggregation:
  - Attention-weighted pooling over unit sequence (NOT sum or mean)
  - Learn a query vector q ∈ R^64
  - attention_weights = softmax(units @ q / sqrt(64))
  - pooled = weighted sum of units by attention_weights
  - This learns to focus on the carry, not average over all units

Prediction Head:
  Concatenate:
    - player_pooled (64)
    - opponent_pooled (64)
    - player_global (64)  — traits, augments, game state
    - opponent_global (64)
    - element-wise difference: player_pooled - opponent_pooled (64)
    - element-wise product: player_pooled * opponent_pooled (64)
  Total: 384 dimensions
  
  MLP:
    nn.Linear(384, 256) -> LayerNorm -> GELU -> Dropout(0.15)
    nn.Linear(256, 128) -> LayerNorm -> GELU -> Dropout(0.15)
    nn.Linear(128, 64) -> GELU
    nn.Linear(64, num_outputs)
  
  Output heads (multi-task):
    - fight_win: sigmoid(Linear(64, 1))      — P(player wins this fight)
    - damage_dealt: ReLU(Linear(64, 1))       — Expected damage dealt
    - placement: Linear(64, 8) -> softmax     — Placement distribution
    - board_strength: Linear(64, 1)           — Scalar board power rating

Loss function (multi-task weighted):
  loss = 1.0 * BCE(fight_win, target_win)
       + 0.3 * MSE(damage_dealt, target_damage)
       + 0.5 * CrossEntropy(placement, target_placement)
       + 0.2 * MSE(board_strength, target_strength)
  
  Where target_strength = board_strength_parameters.m * win_rate + board_strength_parameters.c
  (from model_lookups: m=38.097, c=25.491)

TOTAL PARAMETER COUNT TARGET: ~500K - 2M parameters
This is intentionally small. TFT boards are small (14 units max).
Don't over-parameterize.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class AttentionPooling(nn.Module):
    """Learned attention-weighted pooling over a sequence.
    
    Instead of mean/sum pooling (which treats all units equally),
    learn to focus on the most important units (carries > supports).
    """
    def __init__(self, embed_dim: int):
        super().__init__()
        self.query = nn.Parameter(torch.randn(embed_dim))
    
    def forward(self, x: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
        # x: (batch, seq_len, embed_dim)
        # mask: (batch, seq_len) — True for valid, False for padding
        # Returns: (batch, embed_dim)
        scores = torch.matmul(x, self.query) / (x.size(-1) ** 0.5)
        if mask is not None:
            scores = scores.masked_fill(~mask, float('-inf'))
        weights = F.softmax(scores, dim=1)
        return torch.sum(x * weights.unsqueeze(-1), dim=1)


class TFTTransformerV2(nn.Module):
    """Main transformer model. Implement the full architecture above."""
    pass
```

### Step 2.3: Training Loop

Create `models/train_transformer.py`.

```python
"""
Training script for TFTTransformerV2.

Usage:
    python -m models.train_transformer \
        --data training_data/1M \
        --epochs 50 \
        --batch-size 512 \
        --lr 3e-4 \
        --output models/checkpoints/transformer_v1

TRAINING CONFIGURATION:

Optimizer: AdamW
  - lr: 3e-4
  - weight_decay: 0.01
  - betas: (0.9, 0.98)

Scheduler: OneCycleLR
  - max_lr: 3e-4
  - pct_start: 0.1 (10% warmup)
  - anneal_strategy: 'cos'

Batch size: 512 (increase if GPU memory allows)
Epochs: 50 (with early stopping patience=10)

Data pipeline:
  - Use PyTorch DataLoader with num_workers=4
  - Pin memory for GPU transfer
  - Shuffle training data each epoch
  - Stratify train/val/test by game_id (no data leakage between games)
    CRITICAL: Splits must be by GAME, not by ROW.
    Rows from the same game are correlated — if any row from game X
    is in training, ALL rows from game X must be in training.

Logging:
  - Print loss every 100 batches
  - Evaluate on validation set every epoch
  - Save best model by validation AUC
  - Log to tensorboard: loss curves, learning rate, gradient norms
  - Save training config as JSON alongside checkpoint

Gradient clipping: max_norm=1.0

Mixed precision: Use torch.cuda.amp.autocast() + GradScaler for speed
"""
```

### Step 2.4: PyTorch Dataset

Create `models/dataset.py`.

```python
"""
PyTorch Dataset for TFT training data.

This bridges the gap between raw parquet/JSONL data and the transformer's
expected input format.

CRITICAL IMPLEMENTATION DETAIL:
The transformer expects STRUCTURED input, not flat feature vectors.
Each sample must preserve the per-unit structure:

Sample = {
    # Player side
    "player_champion_ids": LongTensor(14),      # champion indices
    "player_star_levels": LongTensor(14),        # 0-3 (0=empty)
    "player_items": LongTensor(14, 3),           # item indices per unit
    "player_positions": LongTensor(14),           # hex position indices
    "player_costs": LongTensor(14),               # cost tier per unit
    "player_mask": BoolTensor(14),                # True for real units
    "player_traits": FloatTensor(53),             # trait activation levels
    "player_augments": LongTensor(3),             # augment indices
    "player_game_state": FloatTensor(6),          # level, hp, gold, streak, round, stage
    
    # Opponent side (same structure)
    "opponent_champion_ids": LongTensor(14),
    ...
    
    # Targets
    "fight_result": FloatTensor(1),               # 0.0 or 1.0
    "damage_dealt": FloatTensor(1),
    "placement": LongTensor(1),                   # 0-7 (for CrossEntropy)
}

Padding: Units beyond the player's actual count are padded with zeros.
The mask tensor tells the model which slots are real.

You MUST create an encoding lookup that maps:
  - Champion apiName (e.g. "TFT16_Fiddlesticks") → integer index
  - Item apiName (e.g. "TFT_Item_GuardianAngel") → integer index  
  - Augment apiName → integer index
  
Load these from:
  - simulator/data/combat_data.json for champions
  - data/api/processed/augments_set16.json for augments
  - Item data from the items.jsonl or simulator item catalog
"""
```

---

## PHASE 3: Bayesian Uncertainty Quantification

### Goal

Add calibrated uncertainty estimates to every prediction. This is the difference between "you'll win" and "you'll probably win but it's close." Essential for coaching — uncertain predictions should be flagged differently from confident ones.

### Step 3.1: MC Dropout Implementation

Create `models/uncertainty.py`.

```python
"""
Bayesian uncertainty via Monte Carlo Dropout.

THEORY:
  Running the same input through the model N times with dropout ENABLED
  at inference time approximates sampling from the posterior distribution
  over model weights. The variance of these N predictions is the model's
  epistemic uncertainty (what it doesn't know).

IMPLEMENTATION:

class BayesianPredictor:
    def __init__(self, model: TFTTransformerV2, n_samples: int = 30):
        self.model = model
        self.n_samples = n_samples
    
    def predict_with_uncertainty(self, batch) -> dict:
        self.model.train()  # CRITICAL: keeps dropout active
        
        predictions = []
        for _ in range(self.n_samples):
            with torch.no_grad():
                pred = self.model(batch)
            predictions.append(pred)
        
        # Stack predictions: (n_samples, batch, output_dim)
        stacked = torch.stack(predictions)
        
        # Mean prediction
        mean = stacked.mean(dim=0)
        
        # Epistemic uncertainty (model uncertainty)
        epistemic = stacked.var(dim=0)
        
        # For classification (fight_win):
        # Aleatoric uncertainty ≈ mean of p(1-p) across samples
        # Epistemic uncertainty ≈ variance of p across samples
        p_samples = torch.sigmoid(stacked[..., 0])  # fight_win logits
        aleatoric = (p_samples * (1 - p_samples)).mean(dim=0)
        epistemic_cls = p_samples.var(dim=0)
        total_uncertainty = aleatoric + epistemic_cls
        
        return {
            "fight_win_prob": p_samples.mean(dim=0),
            "fight_win_aleatoric": aleatoric,      # Inherent randomness
            "fight_win_epistemic": epistemic_cls,   # Model ignorance
            "fight_win_total_uncertainty": total_uncertainty,
            "confidence": 1.0 - total_uncertainty,  # For UI display
            
            "placement_distribution": F.softmax(stacked[..., 2:10].mean(dim=0), dim=-1),
            "placement_uncertainty": stacked[..., 2:10].var(dim=0).sum(dim=-1),
            
            # Confidence categories for coaching UI:
            # "high_confidence": total_uncertainty < 0.05
            # "medium_confidence": 0.05 <= total_uncertainty < 0.15
            # "low_confidence": total_uncertainty >= 0.15
            # "coin_flip": 0.45 <= fight_win_prob <= 0.55 and uncertainty > 0.1
        }

CALIBRATION:
  After training, verify calibration:
  - Bin predictions into 10 buckets by predicted probability
  - For each bucket, compute actual win rate
  - If model says "70% win", actual win rate should be ~70%
  - If not calibrated, apply temperature scaling:
    logits_calibrated = logits / T
    where T is learned on validation set via NLL minimization
"""
```

---

## PHASE 4: Causal Counterfactual Engine

### Goal

Answer "what if" questions using the simulator. This is the killer coaching feature that no existing TFT tool offers. Instead of just predicting "your board is weak," it tells you "if you swap Jinx for Fiddlesticks, your expected placement improves by 1.3 positions."

### Step 4.1: Counterfactual Simulator

Create `models/counterfactual.py`.

```python
"""
Causal counterfactual analysis via simulation.

THEORY:
  Standard ML: P(win | board_state) — observational
  Causal:      P(win | do(change)) — interventional
  
  The do-operator means "what happens if I FORCE this change?"
  We can compute this exactly because we have a simulator.

IMPLEMENTATION:

class CounterfactualEngine:
    def __init__(self, simulator, model, n_simulations: int = 200):
        self.simulator = simulator  # The combat simulator
        self.model = model          # Trained transformer (for fast estimates)
        self.n_simulations = n_simulations
    
    def evaluate_swap(
        self,
        current_board: BoardState,
        opponent_board: BoardState,
        unit_to_remove: str,       # Champion apiName to remove
        unit_to_add: str,          # Champion apiName to add
        items_to_transfer: bool = True
    ) -> dict:
        """
        Compute Average Treatment Effect (ATE) of swapping one unit.
        
        ATE = E[outcome | do(swap)] - E[outcome | do(nothing)]
        
        Steps:
        1. Run N simulations with current board → baseline win rate
        2. Create modified board with the swap
        3. Run N simulations with modified board → treatment win rate
        4. ATE = treatment_win_rate - baseline_win_rate
        5. Compute 95% CI for ATE using normal approximation:
           SE = sqrt(p1(1-p1)/n + p2(1-p2)/n)
           CI = ATE ± 1.96 * SE
        """
        pass
    
    def evaluate_item_change(
        self,
        current_board: BoardState,
        opponent_board: BoardState,
        unit: str,                 # Which unit to modify
        item_to_remove: str,       # Item to remove (None if adding)
        item_to_add: str,          # Item to add
    ) -> dict:
        """ATE of changing an item on a unit."""
        pass
    
    def evaluate_position_change(
        self,
        current_board: BoardState,
        opponent_board: BoardState,
        unit: str,
        new_position: int,         # New hex index (0-27)
    ) -> dict:
        """ATE of repositioning a unit."""
        pass
    
    def recommend_best_swap(
        self,
        current_board: BoardState,
        opponent_board: BoardState,
        available_champions: List[str],  # Champions in shop/bench
        top_k: int = 5
    ) -> List[dict]:
        """
        Evaluate all possible single-unit swaps and return top K
        by expected placement improvement.
        
        For efficiency:
        1. Use the FAST model prediction for initial screening of all swaps
        2. Run FULL simulation only on top 20 candidates
        3. Return top K with full ATE + confidence intervals
        
        This is a two-stage approach:
        Stage 1 (model, ~1ms per eval): Score all possible swaps
        Stage 2 (simulator, ~1s per eval): Validate top 20
        """
        pass
    
    def recommend_full_pivot(
        self,
        current_board: BoardState,
        opponent_boards: List[BoardState],  # All 7 opponents
        available_resources: dict,           # Gold, shop, bench, items
        personal_performance: dict,          # From performance_reference.json
    ) -> List[dict]:
        """
        High-level coaching recommendation.
        
        Consider:
        1. Which compositions can you transition to given your resources?
        2. For each reachable comp, what's the expected placement?
        3. Weight by personal performance history (AP > AD for this player)
        4. Factor in lobby contestation (if 3 others play same comp, avoid it)
        5. Return top 3 recommendations with reasoning
        """
        pass
```

---

## PHASE 5: Stochastic Game Trajectory Modeling

### Goal

Model the entire 8-player game as a stochastic process to answer "what's my probability of top 4 from HERE?" at any point in the game.

### Step 5.1: Markov Chain Placement Model

Create `models/trajectory.py`.

```python
"""
Game trajectory modeling via absorbing Markov chains.

THEORY:
  Model the game as a Markov chain where:
  - State: vector of 8 player HPs (each 0-100)
  - Absorbing states: any state where a player reaches 0 HP
  - Transition probabilities: derived from combat simulator
  
  Key insight: We don't need the full HP-vector state space.
  Discretize each player's HP into buckets: [0, 1-25, 26-50, 51-75, 76-100]
  That's 5^8 = 390,625 states — tractable for sparse matrix methods.

  Or better: model each player independently conditioned on round + level + board strength.
  P(hp_next | hp_current, round, board_strength, opponent_strength)

IMPLEMENTATION:

class GameTrajectoryModel:
    def __init__(self, transition_model, n_simulations=1000):
        pass
    
    def compute_top4_probability(
        self,
        current_game_state: dict,  # All 8 players' boards + HPs
        player_index: int,         # Which player are we coaching?
    ) -> dict:
        """
        Monte Carlo estimate of top-4 probability from current state.
        
        Method:
        1. Take the current game state (8 players, their boards, HPs)
        2. Run the FULL game simulator forward N times from this state
        3. Record the coached player's final placement each time
        4. Return:
           - P(top 4) = count(placement <= 4) / N
           - P(1st) through P(8th) = placement distribution
           - Expected placement = mean placement
           - 95% CI via Wilson interval
        """
        pass
    
    def compute_hp_trajectory(
        self,
        current_game_state: dict,
        player_index: int,
        n_rounds_forward: int = 10,
    ) -> dict:
        """
        Simulate HP trajectories forward and return percentile bands.
        
        Returns:
           - median_hp[round] for each future round
           - p10_hp[round], p25_hp[round], p75_hp[round], p90_hp[round]
           - elimination_probability[round] = P(hp=0 by this round)
           
        This produces a "fan chart" showing the range of possible HP futures.
        Essential for coaching: "you can afford to lose-streak 3 more rounds"
        vs "you need to stabilize NOW or you're out."
        """
        pass
    
    def survival_analysis(
        self,
        current_game_state: dict,
        player_index: int,
    ) -> dict:
        """
        Compute the survival function S(t) = P(alive at round t).
        
        Uses Kaplan-Meier estimator across N simulations:
        S(t) = ∏(t_i <= t) (1 - d_i / n_i)
        where d_i = deaths at round i, n_i = at-risk at round i
        
        Returns:
           - survival_function: list of (round, probability) pairs
           - median_survival: round at which S(t) crosses 0.5
           - expected_rounds_remaining: area under survival curve
        """
        pass
```

---

## PHASE 6: Information-Theoretic Feature Analysis

### Step 6.1: Mutual Information Analysis

Create `models/information_theory.py`.

```python
"""
Information-theoretic analysis of feature importance.

Run this AFTER Phase 1 XGBoost training to mathematically quantify
which features carry the most predictive signal.

IMPLEMENTATION:

1. MARGINAL MUTUAL INFORMATION
   For each feature X_i and target Y:
   I(X_i; Y) = H(Y) - H(Y|X_i)
   
   Use sklearn.feature_selection.mutual_info_classif for classification
   Use sklearn.feature_selection.mutual_info_regression for placement
   
   This tells you: "How much does knowing this feature reduce uncertainty
   about the outcome?"

2. CONDITIONAL MUTUAL INFORMATION (for redundancy detection)
   I(X_i; Y | X_j) = how much does X_i add GIVEN you already know X_j?
   
   If I(X_i; Y | X_j) ≈ 0, then X_i is redundant given X_j.
   If I(X_i; Y | X_j) ≈ I(X_i; Y), then X_i is complementary to X_j.
   
   Compute for all pairs in the top 30 features.
   Use conditional_mutual_info from pyitlib or implement via KDE.

3. INTERACTION INFORMATION (synergistic features)
   II(X_i; X_j; Y) = I(X_i; X_j; Y) - I(X_i; Y) - I(X_j; Y) + I(X_i; X_j)
   
   Positive II = synergy: knowing both features together is more valuable
   Negative II = redundancy: overlapping information
   
   This identifies feature PAIRS that the model should attend to.
   Maps directly to what the transformer's attention should learn.

4. FEATURE SUFFICIENCY CURVE
   Sort features by mutual information (descending).
   Train XGBoost with top-1, top-2, ..., top-N features.
   Plot accuracy vs number of features.
   
   The "knee" of this curve tells you how many features you actually need.
   If accuracy plateaus at 30 features, features 31+ are noise.

OUTPUT:
   Save as models/analysis/feature_information.json:
   {
       "marginal_mi": {"feature_name": mi_value, ...},
       "top_20_features_by_mi": [...],
       "redundant_pairs": [["feat_a", "feat_b", conditional_mi], ...],
       "synergistic_pairs": [["feat_a", "feat_b", interaction_info], ...],
       "sufficiency_curve": [{"n_features": k, "accuracy": acc}, ...]
   }
"""
```

---

## DEPENDENCY INSTALLATION

Create `requirements-ml.txt`:

```
# Core ML
torch>=2.1.0
xgboost>=2.0.0
lightgbm>=4.0.0
scikit-learn>=1.3.0

# Data handling
pyarrow>=14.0
pandas>=2.1.0
numpy>=1.24.0

# Visualization
matplotlib>=3.8.0
seaborn>=0.13.0

# Logging
tensorboard>=2.15.0

# Information theory
scipy>=1.11.0

# Optional but recommended
tqdm>=4.66.0
rich>=13.0.0        # Pretty console output

# For mutual information (Phase 6)
# pyitlib>=0.2.2    # Optional — can compute with sklearn instead
```

Install:
```bash
pip install -r requirements-ml.txt --break-system-packages
```

---

## BUILD ORDER & MILESTONES

Execute these in order. Each phase builds on the previous.

| Phase | What | Est. Time | Success Metric |
|-------|------|-----------|----------------|
| 1.1 | Feature engineering module | 4 hours | All 7 feature groups implemented, unit tests pass |
| 1.2 | Data loader | 2 hours | Can load parquet chunks into numpy arrays |
| 1.3 | XGBoost training | 2 hours | Fight accuracy >65%, top4 accuracy >70% |
| 1.4 | Generate 10K games | 4 hours (compute) | 10K games in training_data/ |
| 1.5 | Evaluation suite | 3 hours | Full report with CIs, feature importance, calibration |
| 2.1 | Embeddings module | 4 hours | All encoders produce correct output shapes |
| 2.2 | Transformer architecture | 6 hours | Forward pass runs, parameter count ~1M |
| 2.3 | Training loop | 4 hours | Loss decreases, AUC improves on val set |
| 2.4 | Dataset & 1M data gen | 15 hours (compute) | 1M games generated, dataset loads correctly |
| 3.1 | Bayesian uncertainty | 3 hours | Calibrated uncertainty estimates |
| 4.1 | Counterfactual engine | 6 hours | ATE computed with CIs for unit swaps |
| 5.1 | Trajectory model | 6 hours | Top4 probability from mid-game states |
| 6.1 | Information theory | 3 hours | Feature MI analysis report generated |

**TOTAL: ~62 hours of coding + ~19 hours of compute**

---

## TESTING REQUIREMENTS

For every module, create a corresponding test file in `tests/`.

```
tests/
├── test_feature_engineering.py   # Test each feature group with known inputs
├── test_data_loader.py           # Test parquet/JSONL loading
├── test_embeddings.py            # Test output shapes, padding, masking
├── test_transformer.py           # Test forward pass, gradient flow
├── test_uncertainty.py           # Test MC dropout produces variance
├── test_counterfactual.py        # Test ATE computation
├── test_trajectory.py            # Test survival analysis
└── test_information_theory.py    # Test MI computation
```

Key test patterns:

```python
# ALWAYS test that padding masks work correctly
def test_padding_mask():
    """Empty unit slots should not affect predictions."""
    # Create board with 5 units
    board_5 = make_board(n_units=5)
    # Create same board with 5 units + 9 padding slots
    board_5_padded = pad_to_14(board_5)
    # Predictions should be identical
    pred_5 = model(board_5)
    pred_padded = model(board_5_padded)
    assert torch.allclose(pred_5, pred_padded, atol=1e-5)

# ALWAYS test that unit order doesn't matter (permutation invariance)
def test_permutation_invariance():
    """Shuffling unit order should not change predictions (within tolerance)."""
    board = make_board(n_units=8)
    shuffled = shuffle_units(board)
    pred_original = model(board)
    pred_shuffled = model(shuffled)
    # Note: with positional encoding, this WON'T be exactly equal
    # But without position features, it should be
    assert torch.allclose(pred_original, pred_shuffled, atol=1e-4)

# ALWAYS test that the model differentiates strong vs weak boards
def test_strong_vs_weak():
    """3-star 5-costs with BIS items should beat 1-star 1-costs."""
    strong = make_strong_board()  # Level 9, 3-star Fiddle with Blue Buff etc.
    weak = make_weak_board()      # Level 3, 1-star 1-costs, no items
    pred = model(strong, weak)
    assert pred["fight_win_prob"] > 0.9
```

---

## CRITICAL WARNINGS

1. **Data leakage**: ALWAYS split by game_id, not by row. Rows from the same game share the same players, economy states, and compositions. Splitting randomly will inflate accuracy.

2. **Class imbalance**: In 8-player games, only 1 player gets 1st. Placement prediction will be imbalanced. Use stratified sampling and weighted loss functions.

3. **Simulator bias**: The model inherits whatever systematic errors exist in the combat simulator. If the simulator incorrectly handles a champion ability, the model will learn that incorrect behavior. Validate against real match data when possible.

4. **Feature scaling**: XGBoost doesn't need feature scaling. The transformer DOES. Use LayerNorm inside the architecture (already specified above). For input scalars (HP, gold, etc.), normalize to [0, 1] range.

5. **Champion encoding**: Use the EXACT apiNames from `combat_data.json` (e.g., `TFT16_Fiddlesticks`, not `Fiddlesticks`). The name_converter.py handles mapping but the ML pipeline should use apiNames as canonical IDs.

6. **Augment tiers**: Augment tier (silver/gold/prismatic) is NOT directly stored in the augment name. Load from `augments_set16.json` which contains tier metadata. Some augments shift tiers via `TFT_Augment_PowerUp` etc.

7. **7-cost champions**: These share 5-cost shop odds but use different buy/sell gold values. Treat them as cost tier 7 in features, not 5.

8. **The 6 non-shop units**: `TFT16_AnnieTibbers`, `TFT16_Atakhan`, `TFT16_AzirSoldier`, `TFT16_FreljordProp`, `TFT16_MalzaharVoidling`, `TFT16_PiltoverInvention` appear in combat but NOT in the shop pool. They must be in the champion vocabulary but flagged as non-rollable.

---

## FILE CREATION CHECKLIST

When done, the `models/` directory should contain:

```
models/
├── __init__.py
├── feature_engineering.py      # Phase 1 — Feature extraction
├── data_loader.py              # Phase 1 — Parquet/JSONL loading
├── train_xgboost.py            # Phase 1 — XGBoost training + evaluation
├── evaluate.py                 # Phase 1 — Comprehensive evaluation suite
├── embeddings.py               # Phase 2 — Unit/item/position embeddings
├── transformer.py              # Phase 2 — TFTTransformerV2 architecture
├── dataset.py                  # Phase 2 — PyTorch Dataset class
├── train_transformer.py        # Phase 2 — Transformer training loop
├── uncertainty.py              # Phase 3 — Bayesian MC Dropout
├── counterfactual.py           # Phase 4 — Causal what-if engine
├── trajectory.py               # Phase 5 — Game trajectory modeling
├── information_theory.py       # Phase 6 — MI analysis
├── checkpoints/                # Saved model weights
├── analysis/                   # Feature importance, MI reports
└── configs/                    # Training hyperparameter configs
```
