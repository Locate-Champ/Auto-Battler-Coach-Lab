# Knowledge Base

This folder is the durable home for knowledge-base sources, manifests, and future processing outputs.

## Folder roles

- `sources/`: Raw and intermediate content collected from external sources.
- `manifests/`: Inventories that describe the sources and their processing state.

Within `sources/web-scrape/`:

- `incoming/`: Raw, freshly uploaded markdown files from crawl4ai.
- `canonical/`: Normalized filenames and consistent markdown cleanup (future phase).
- `processed/`: Derived outputs such as chunked or enriched markdown (future phase).
- `metadata/`: URL maps, crawl stats, and other supporting metadata (future phase).

## How to add a new source

1. Place new markdown files into the appropriate `sources/<source-name>/incoming/` folder.
2. Keep original filenames when possible to preserve traceability.
3. Add or update a manifest entry in `manifests/` after upload (Phase 2).
