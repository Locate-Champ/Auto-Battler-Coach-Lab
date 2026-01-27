# Claude Project Upload Guide

## Condensed Files for Upload (Recommended)

These 2 files contain ALL essential project knowledge condensed:

| File | Size | Contents |
|------|------|----------|
| `TFT_COACH_PROJECT_KNOWLEDGE.md` | ~7 KB | UI specs, colors, layout, algorithm, performance data, component hierarchy |
| `performance_reference.json` | ~5 KB | Structured carry/item/trait stats, comp archetypes, UI colors |

**Total: ~12 KB** (vs ~13 MB of original scattered files)

---

## What Was Condensed

### Design Specs (Combined into TFT_COACH_PROJECT_KNOWLEDGE.md)
- Figma_Resources_Guide.md
- TFT_Coach_Figma_Spec.md
- TFT_Coach_Component_Outline.js

### Performance Data (Combined into performance_reference.json)
- carry_performance_corrected.csv
- item_performance_corrected.csv
- trait_performance_corrected.csv

---

## Files You Can Remove from Claude Project

### Exact Duplicates (already in API Data)
These files exist in both locations with identical content:
- comp_builds.json (5.3 MB)
- comp_options.json (4.6 MB)
- comps_data.json (269 KB)
- comps_stats.json (6 KB)
- unit_items_processed.json (140 KB)

### Redundant JSONL Files
The `tft project files` folder JSONL files are duplicates of what's in `data/game_data/`:
- ability_variables.jsonl
- augments.jsonl
- champion_traits.jsonl
- champions.jsonl
- items.jsonl
- trait_effects.jsonl
- traits.jsonl
- set16_*.jsonl files

### Empty/Placeholder Files
- blank (0 bytes)
- item_components.jsonl (0 bytes)

---

## Recommended Claude Project Structure

Upload these files in order of priority:

### Priority 1: Core Knowledge (12 KB total)
```
TFT_COACH_PROJECT_KNOWLEDGE.md   <- All UI/design specs condensed
performance_reference.json        <- All performance data structured
```

### Priority 2: If Space Allows
```
data/api/processed/index.json     <- Quick reference of available data
data/API_DATA_README.json         <- Data organization documentation
```

### Priority 3: Raw Data (only if needed for lookups)
```
data/api/processed/units_set16.json     <- 116 units
data/api/processed/items_set16.json     <- 270 items
data/api/processed/augments_set16.json  <- 397 augments
data/api/processed/traits_set16.json    <- 53 traits
```

---

## Quick Copy Commands

To copy the condensed files to a folder for upload:
```bash
mkdir -p ~/tft-claude-upload
cp knowledge-base/TFT_COACH_PROJECT_KNOWLEDGE.md ~/tft-claude-upload/
cp knowledge-base/performance_reference.json ~/tft-claude-upload/
```
