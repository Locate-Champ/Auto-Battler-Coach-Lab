# TFT Match Data Integration Plan

## Overview

New data file `tft_matches_since_set16.csv` contains **864 matches** from Set 16 - a significant upgrade from the current 163 matches in `tft_since_16_2_enhanced.csv` (5x more data).

---

## 1. Data Analysis

### New File Structure
| Column | Type | Example |
|--------|------|---------|
| match_id | string | `NA1_5476909392` |
| game_datetime | timestamp | `1.76957E+12` (epoch ms) |
| game_length_sec | float | `2173.15332` |
| queue_id | int | `1100` (ranked), `1220` (other) |
| game_version | string | `Linux Version 16.2.741.3171...` |
| placement | int | 1-8 |
| level | int | 1-9 |
| gold_left | int | End-game gold |
| last_round | int | Final round number |
| time_eliminated | float | Time when eliminated |
| total_damage_to_players | int | Damage dealt |
| players_eliminated | int | Kills |
| 1-Aug, 2-Aug, 3-Aug | string | Augment slots (mostly empty) |
| traits_active | string | `TFT16_Juggernaut:1 \| TFT16_Noxus:2` |
| final_board_units | string | `Sion_2*(BrambleVest,DragonsClaw) \| ...` |

### Riot Backend Version Mapping

**Important:** Riot's backend version IDs are offset from the public patch numbers:

| Backend Version | Actual Patch | Games | Release Date |
|-----------------|--------------|-------|--------------|
| 15.24 | **16.1** | 600 | 12/3/2025 |
| 16.1 | **16.2** | 165 | 1/8/2026 |
| 16.2 | **16.3** | 99 | 1/22/2026 (current) |

The preprocessing script must translate backend versions to actual patch numbers.

### Key Differences from Current Data

| Aspect | Current File | New File |
|--------|-------------|----------|
| Matches | 163 | 864 |
| Trait format | `Brawler:1` | `TFT16_Brawler:1` |
| Augment columns | `aug1, aug2, aug3` | `1-Aug, 2-Aug, 3-Aug` |
| Patch coverage | 16.2 only | 16.1, 16.2, 16.3 |

---

## 2. Integration Tasks

### Phase 1: Data Preprocessing Script
Create a new script `scripts/process_riot_matches.py` that:

1. **Normalizes trait names** - Strip `TFT16_` prefix to match existing format
2. **Standardizes column names** - Rename `1-Aug` to `aug1`, etc.
3. **Deduplicates matches** - Check for overlapping match_ids between files
4. **Validates data quality** - Check for missing values, outliers
5. **Exports cleaned CSV** - Save to `data/personal/tft_all_matches.csv`

```python
# Pseudo-code for preprocessing
def normalize_traits(traits_str):
    # "TFT16_Brawler:1 | TFT16_Void:2" -> "Brawler:1 | Void:2"
    return re.sub(r'TFT16_', '', traits_str)

def standardize_columns(df):
    rename_map = {'1-Aug': 'aug1', '2-Aug': 'aug2', '3-Aug': 'aug3'}
    return df.rename(columns=rename_map)

def map_backend_to_patch(backend_version):
    # Riot backend versions are offset from public patch numbers
    VERSION_MAP = {
        '15.24': '16.1',
        '16.1': '16.2',
        '16.2': '16.3',
    }
    return VERSION_MAP.get(backend_version, backend_version)
```

### Phase 2: Feature Engineering Updates
Update `src/models/feature_engineering.py` to:

1. **Handle both trait formats** - Accept with/without TFT16_ prefix
2. **Add new features**:
   - `patch_version` - Extract from game_version (16.1 vs 16.2)
   - `queue_type` - Ranked (1100) vs other modes
   - `game_duration_category` - Fast (<25min), Medium, Long (>35min)
3. **Include augment features** when available

### Phase 3: Playstyle Analysis (Primary Use Case)

**Important:** Historical patch data (16.1, 16.2) should be used for **playstyle profiling only**, not meta recommendations. Balance changes between patches make comp-specific win rates unreliable across patches.

Use all 864 games to identify:
1. **Carry type performance** - AP vs AD carry win rates (user-specific)
2. **Trait affinity** - Which trait combinations the user executes well
3. **Cost curve preferences** - Fast 8 vs slow roll vs hyper roll tendencies
4. **Positioning patterns** - Frontline/backline ratios, item distribution

Do NOT use historical data for:
- "This comp is strong" (meta-dependent)
- "Build this item" (balance changes)
- Specific unit recommendations (buffs/nerfs shift tier lists)

### Phase 4: Model Training
With 5x more data:

1. **Playstyle classifier** - Identify user's preferred archetypes
2. **Carry performance model** - Predict success based on carry type + user history
3. **Cross-validation** - Now feasible with larger dataset
4. **Current patch validation** - Verify playstyle patterns hold in 16.3 (99 games)

### Phase 5: API Integration
Update `app/api/server.py` to:

1. **Serve updated statistics** - Use new combined dataset
2. **Add patch filter** - Allow filtering by game version
3. **Queue type filter** - Separate ranked vs casual stats

---

## 3. Expected Benefits

### ML Model Improvements
| Metric | Before (163 games) | After (864 games) |
|--------|-------------------|-------------------|
| Training samples | ~130 (80% split) | ~690 |
| Validation samples | ~33 | ~174 |
| Feature stability | Low | High |
| Overfitting risk | High | Moderate |

### Statistical Analysis
- **Carry analysis**: More reliable AP vs AD carry statistics
- **Trait analysis**: Better understanding of synergy performance
- **Item analysis**: Larger sample for item win rates
- **Augment analysis**: More data for augment recommendations

---

## 4. Implementation Order

```
[ ] 1. Create scripts/process_riot_matches.py
    - Load both CSV files
    - Normalize traits (strip TFT16_ prefix)
    - Standardize column names
    - Deduplicate by match_id
    - Export combined data

[ ] 2. Validate combined dataset
    - Check for data quality issues
    - Verify trait/unit parsing still works
    - Run feature engineering test

[ ] 3. Update feature engineering
    - Add patch version feature
    - Add queue type feature
    - Handle both trait formats

[ ] 4. Retrain ML models
    - Placement prediction with more data
    - Update carry type analysis
    - Recalculate statistics

[ ] 5. Update API endpoints
    - Load new data file
    - Add filtering options
    - Update stats responses

[ ] 6. Archive old data file
    - Move tft_since_16_2_enhanced.csv to archive
    - Update CLAUDE.md references
```

---

## 5. Quick Start Commands

```bash
# Step 1: Process and combine data
python scripts/process_riot_matches.py

# Step 2: Verify feature engineering
python -m src.models.feature_engineering

# Step 3: Retrain model
python -m src.models.placement_model

# Step 4: Start app with new data
npm start
```

---

## 6. Data Quality Notes

### Observations from new data:
- Queue ID 1100 = Ranked TFT
- Queue ID 1220 = Other modes (Hyper Roll?)
- Some games have very short durations (surrender/early losses)
- Augment data is sparse in the new file (mostly 0 or empty)
- Unit format is consistent: `Name_Star*(Item1,Item2,...)`

### Special units detected:
- `tft16_atakhan_1*()` - Noxus boss unit (lowercase)
- `AnnieTibbers_1*()` - Summoned unit
- Various emblem items: `TFT16_Item_VoidEmblemItem`

---

## 7. Rollback Plan

If issues arise:
1. Keep original file at `data/personal/tft_since_16_2_enhanced.csv`
2. New processing outputs to `data/personal/tft_all_matches.csv`
3. Feature engineering defaults to new file but accepts path parameter
4. Can switch back by updating CSV path in config

---

*Created: 2026-02-02*
