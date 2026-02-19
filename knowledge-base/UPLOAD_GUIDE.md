# Knowledge Base Upload Guide

## Quick Upload

Place markdown files in:
```
knowledge-base/sources/web-scrape/incoming/
```

After upload, run:
```bash
python scripts/kb/build_manifest.py
```

---

## Condensed Files for Claude Project

These 2 files contain ALL essential project knowledge:

| File | Size | Contents |
|------|------|----------|
| `AUTO_BATTLER_COACH_PROJECT_KNOWLEDGE.md` | ~7 KB | UI specs, colors, layout, performance data |
| `performance_reference.json` | ~5 KB | Structured carry/item/trait stats |

**Total: ~12 KB** (vs ~13 MB of scattered files)

### Copy Command
```bash
mkdir -p ~/coach-claude-upload
cp knowledge-base/AUTO_BATTLER_COACH_PROJECT_KNOWLEDGE.md ~/coach-claude-upload/
cp knowledge-base/performance_reference.json ~/coach-claude-upload/
```

---

## Files to Remove (Duplicates)

These exist in multiple locations:
- `comp_builds.json`, `comp_options.json`, `comps_data.json`
- JSONL files in `game project files/` (duplicate of `data/game_data/`)
- Empty files: `blank`, `item_components.jsonl`

---

## Recommended Upload Priority

1. **Core Knowledge**: `AUTO_BATTLER_COACH_PROJECT_KNOWLEDGE.md`, `performance_reference.json`
2. **If needed**: `data/api/processed/index.json`, `data/API_DATA_README.json`
3. **Raw data**: `data/api/processed/*.json` files

