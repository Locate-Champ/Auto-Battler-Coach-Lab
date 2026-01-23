# Manifests

Manifests describe the markdown files in `knowledge-base/sources/` for downstream use.

## Regenerating

Run the manifest builder to inventory incoming files and refresh the manifest outputs:

```bash
python scripts/kb/build_manifest.py
```

Outputs are written to:

- `knowledge-base/manifests/manifest.jsonl`
- `knowledge-base/manifests/manifest.json`
- `outputs/kb/manifest-summary.csv`
- `outputs/kb/ingestion-report.md`
- `knowledge-base/sources/web-scrape/metadata/file-map.json`
