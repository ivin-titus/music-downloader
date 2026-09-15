# Development

## Local setup

Requires Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Initialize the default archive:

```bash
music-downloader init
```

Run tests:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

## Package layout

- `src/music_downloader/config.py` — runtime paths and settings
- `src/music_downloader/db.py` — SQLite connection and initial schema
- `src/music_downloader/models.py` — domain objects
- `src/music_downloader/identity.py` — normalization and identity groundwork
- `src/music_downloader/storage.py` — file integrity and atomic filesystem operations
- `src/music_downloader/providers/` — provider adapters
- `src/music_downloader/metadata/` — metadata/artwork enrichment
- `src/music_downloader/pipeline/` — resumable ingestion pipeline
- `src/music_downloader/delivery/` — Telegram/rsync integrations
- `tests/` — unit and integration tests

The current implementation is intentionally small. Provider downloads, metadata corroboration, semantic matching, artwork validation, and delivery integrations will be added incrementally rather than coupling them into the initial skeleton.
