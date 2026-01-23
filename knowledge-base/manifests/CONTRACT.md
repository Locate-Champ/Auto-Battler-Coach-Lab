# Manifest Contract (UI)

The UI can rely on these fields for each manifest entry:

- `id`: stable identifier derived from the file hash.
- `title`: extracted from the first H1 when present, otherwise filename fallback.
- `original_relpath`: path under `knowledge-base/sources/web-scrape/incoming/`.
- `canonical_relpath`: path under `knowledge-base/sources/web-scrape/canonical/`.
- `source`: source label (`web-scrape`).
- `sha256`: full file hash.
- `bytes`: file size in bytes.
- `word_count`: whitespace-based word count.
- `url`: optional; only present when explicitly detected in the file.

Not guaranteed yet:

- Search indexes or embeddings.
- Chunking or section-level metadata.
- Consistent frontmatter or enhanced schemas.
