# TFT Coach Companion - Project Handoff for Claude Code

## Project Objective
Build a TFT coaching companion that provides ML-powered placement predictions and actionable recommendations based on:
1. Historical match performance data (163 games analyzed)
2. Live board state integration via Riot API
3. Current meta data from community sources

**Primary Goal:** Predict placement outcomes and recommend optimal strategies aligned with the user's late-game AP/utility playstyle (70-100% top 4 rate with 5-cost carries like Fiddlesticks, Ornn, Ryze).

---

## File Organization

### 📊 PERSONAL MATCH DATA
| File | Purpose | Records |
|------|---------|---------|
| `tft_since_16_2_enhanced.csv` | **PRIMARY** - 163 matches with full game data | 163 rows |
| `carry_performance_corrected.csv` | Carry unit performance aggregated | 22 carries |
| `trait_performance_corrected.csv` | Trait synergy performance | 54 traits |
| `item_performance_corrected.csv` | Item build performance | 47 items |

**Key columns in match data:**
- `placement` (1-8) - target variable
- `level`, `gold_left`, `last_round`, `time_eliminated` - game state features
- `total_damage_to_players`, `players_eliminated` - performance metrics
- `traits_active` - concatenated trait string (needs parsing)
- `final_board_units` - concatenated unit string (needs parsing)
- `aug1`, `aug2`, `aug3` - augment IDs (floats, some NaN)

### 🎮 SET 16 GAME DATA (CommunityDragon)
| File | Purpose | Records |
|------|---------|---------|
| `champions.jsonl` | All champion base stats & abilities | 101 |
| `champion_traits.jsonl` | Champion → Trait mappings | 207 |
| `ability_variables.jsonl` | Spell scaling by star level | 609 |
| `traits.jsonl` | Trait definitions | 53 |
| `trait_effects.jsonl` | Trait breakpoint variables | 113 |
| `items.jsonl` | All items (completed, components, emblems) | 444 |
| `augments.jsonl` | All augments with effects | 208 |

### 📈 CURRENT META DATA (Patch 16.3)
| File | Purpose |
|------|---------|
| `set16_champions_shop_16_3.jsonl` | Current patch champion data |
| `set16_augments_16_3.jsonl` | Current patch augment data |
| `set16_items_16_3.jsonl` | Current patch item data |
| `metatft_augment_tierlist_16_3.csv` | Community augment tier rankings |
| `tft_set16_3_early_game_stage2_stage3.csv` | Early game comp performance |
| `tft_set16_3_early_game_stage4_stage5.csv` | Mid game comp performance |

### 🎨 UI/DESIGN SPECS
| File | Purpose |
|------|---------|
| `TFT_Coach_Figma_Spec.md` | Complete design system (colors, dimensions, components) |
| `TFT_Coach_Component_Outline.js` | React component architecture |
| `tft_dashboard.html` | Interactive performance dashboard (Chart.js) |
| `Figma_Resources_Guide.md` | Figma MCP integration docs |

### 🔧 UTILITIES
| File | Purpose |
|------|---------|
| `tft_diagnostic.py` | Data parsing and validation utilities |
| `set16_all_records.jsonl` | Merged JSONL with `record_type` field |
| `manifest.json` | File provenance and row counts |
| `metadata.json` | Dataset metadata |

---

## Key Insights from Analysis

### Performance Patterns (from 163 matches)
- **Overall top 4 rate:** 52%
- **AD carries:** 0% top 4 (AVOID)
- **Late-game AP/utility (5-cost carries):** 70-100% top 4
- **Optimal carries:** Fiddlesticks, Ornn, Ryze
- **Underperforming:** AD carries, Bilgewater synergies
- **Strength:** Longer games, higher levels = better outcomes

### Data Parsing Notes
The `traits_active` and `final_board_units` columns contain concatenated strings that need regex parsing:
- Traits format: `TraitName:ActiveCount,...`
- Units format: `UnitName:StarLevel,...`

There's a name mapping challenge between Riot API internal names and display names (400+ mappings needed).

---

## Model Building Objectives

### Phase 1: Placement Prediction Model
**Target:** `placement` (1-8, can treat as regression or classification)

**Features to engineer:**
1. Trait activation counts and specific trait presence
2. Unit composition (cost distribution, star levels)
3. Game state (level, gold, round)
4. Item builds on carries
5. Augment combinations

**Suggested approach:**
- Random Forest or XGBoost for interpretability
- Feature importance analysis to validate insights
- Cross-validation on 163 games (small dataset - be careful of overfitting)

### Phase 2: Recommendation Engine
Based on model insights, recommend:
1. **Optimal pivots** when current comp is underperforming
2. **Item prioritization** based on board state
3. **Augment selection** factoring personal performance

### Phase 3: Live Integration
- Riot API for real-time board state
- Contestation tracking (manual lobby input initially)
- Real-time placement projections

---

## Quick Start Commands

```bash
# Load match data
import pandas as pd
matches = pd.read_csv('tft_since_16_2_enhanced.csv')

# Load performance aggregates
carries = pd.read_csv('carry_performance_corrected.csv')
traits = pd.read_csv('trait_performance_corrected.csv')
items = pd.read_csv('item_performance_corrected.csv')

# Load game data
import json
def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]

champions = load_jsonl('champions.jsonl')
augments = load_jsonl('augments.jsonl')
```

---

## Success Criteria
1. Model achieves >60% accuracy on top 4 vs bottom 4 classification
2. Feature importance aligns with known performance patterns (AP > AD)
3. Recommendations avoid underperforming strategies
4. System can process live game state in <1 second

---

## Notes for Claude Code
- All CSV files use UTF-8 encoding
- JSONL files are newline-delimited JSON
- The diagnostic Python script has useful parsing functions
- Small dataset (163 games) - prioritize interpretable models over complex ones
- User's playstyle favors late-game scaling - weight recommendations accordingly
