# TFT Coach - Instructions for Claude Code

## What This Project Is
A TFT coaching app that predicts placement (1-8) based on board composition. I have 163 matches of personal data showing I'm way better with late-game AP carries (70% top 4) than AD carries (0% top 4).

## What I Need You To Build
A machine learning model that:
1. Predicts placement from board state
2. Identifies which comps/carries/items work best FOR ME
3. Eventually powers recommendations in a React UI

## The Data

**My match history:** `data/personal/tft_since_16_2_enhanced.csv` (163 games)
- Target variable: `placement` (1-8)
- Key features: `traits_active`, `final_board_units`, `level`, `gold_left`, `last_round`

**Already aggregated (in `data/personal/`):**
- `carry_performance_corrected.csv` - which carries I win with
- `trait_performance_corrected.csv` - which traits I win with
- `item_performance_corrected.csv` - which items I win with

**Game reference data:** `data/game_data/*.jsonl` - champion stats, traits, items

## The Tricky Part
The `traits_active` and `final_board_units` columns need parsing:
- Traits: `"Brawler:1 | Void:3"` → split on `|`, then on `:`
- Units: `"KogMaw_2*(Item1,Item2)"` → regex: `(\w+)_(\d)\*\(([^)]*)\)`

There's already parsing code in `src/tft_diagnostic.py` you can use.

## First Task
Build `src/models/feature_engineering.py` that:
1. Loads the match CSV
2. Parses traits into columns (one-hot or counts)
3. Parses units into features (cost distribution, star levels, item counts)
4. Identifies the "carry" (unit with most items)
5. Outputs a clean feature matrix ready for sklearn/xgboost

## Success Criteria
- Model beats 60% accuracy on top4 vs bottom4
- Feature importance confirms AP > AD (validates the data)
- Can explain WHY certain comps work for me

## Don't Worry About
- The React UI yet
- Riot API integration
- Perfect accuracy (163 games is small)

Just get the model working first.
