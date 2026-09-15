# Music Downloader

**Lightweight, resumable, self-hosted personal music archive and playlist synchronizer.**

Music Downloader is designed to turn music from supported sources into a clean, durable personal archive without turning the system into a heavyweight media server.

It focuses on the hard parts that matter for a long-lived archive: **track identity, semantic deduplication, metadata quality, artwork validation, crash-safe downloads, playlist synchronization, and portable storage.**

> **Design principle:** SQLite knows what the archive contains; the filesystem contains the archive; playlists describe relationships to tracks; and identity resolution decides whether different sources represent the same recording.

## Why this exists

Downloading a file is easy. Building a reliable music archive is not.

A source might call the same track:

- `Artist - Song`
- `Artist - Song (Official Video)`
- `Artist – Song [Audio]`
- `Artist - Song (Remastered 2024)`

Some of those are the same recording. Some are not.

Music Downloader therefore treats **source identity** and **musical identity** as separate concepts and uses metadata from multiple sides/providers to make identity decisions instead of using filenames or file hashes alone.

## Key features

- 🎵 **Multi-source ingestion** — provider adapters rather than a single hard-coded source.
- 🔎 **Identity resolution** — compares title, artist, album, duration, identifiers, variants, and corroborating metadata.
- 🧩 **Semantic deduplication** — recognizes the same recording across different encodings/sources without collapsing meaningful variants.
- 🏷️ **Useful lightweight metadata** — reliable title, artist, album, numbering, dates, genre, ISRC, and related fields where available.
- 🖼️ **Validated cover art** — rejects broken images, HTML error pages, and invalid artwork payloads before embedding them.
- 📁 **Source-aware filenames** — preserves the original source title as the primary filename signal, including Unicode and emojis where supported.
- 🔄 **Resumable jobs** — explicit job states, retries, atomic file operations, and crash recovery.
- 📋 **Playlist synchronization** — multiple playlists can reference the same archived track without owning or deleting it.
- 📦 **SQLite archive inventory** — small, portable, transactional source of truth.
- 📤 **Telegram delivery** — optional delivery channel independent from archive correctness.
- 🔐 **rsync over SSH** — additive bulk synchronization to another machine/device.
- 🐳 **Docker-first deployment** — intended for a small always-on host.
- 🪶 **Low resource footprint** — designed around roughly 1 GB RAM and 2 CPU cores.

## Architecture

```text
                         ┌─────────────────────┐
                         │      CLI / API      │
                         └──────────┬──────────┘
                                    │
                         ┌──────────▼──────────┐
                         │ Playlist / Job      │
                         │ Orchestrator        │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
      ┌───────▼───────┐     ┌──────▼───────┐     ┌──────▼───────┐
      │ Source        │     │ Identity      │     │ Metadata +   │
      │ Adapters      │     │ Resolver      │     │ Artwork      │
      └───────┬───────┘     └──────┬───────┘     └──────┬───────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │ Validate + Archive│
                         └─────────┬─────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
             ┌──────▼──────┐              ┌───────▼───────┐
             │   SQLite    │              │ music_files/  │
             │ source of   │              │ durable       │
             │ truth       │              │ archive       │
             └─────────────┘              └───────┬───────┘
                                                 │
                                  ┌──────────────┼──────────────┐
                                  │              │              │
                            ┌─────▼─────┐  ┌────▼─────┐  ┌─────▼─────┐
                            │ Telegram  │  │ rsync/SSH│  │ Backups   │
                            └───────────┘  └──────────┘  └───────────┘
```

## Archive layout

```text
~/music_downloader/
├── app_data/
│   ├── music_downloader.db
│   ├── cache/
│   ├── logs/
│   └── state/
├── music_files/
│   └── Artist/
│       └── Album/
│           └── Track.ext
├── code/
└── docker-compose.yml
```

The important separation is:

- **`music_files/`** — durable music archive.
- **`app_data/`** — database, cache, logs, and operational state.
- **`cache/`** — disposable; safe to rebuild.

The archive should remain usable even if the application is replaced later.

## Identity and deduplication

Music Downloader does **not** assume that two files are different because their hashes differ, nor that two tracks are identical because their titles look similar.

Identity is evaluated using evidence such as:

1. Source/provider identity.
2. Strong identifiers such as ISRC where trustworthy.
3. Agreement between independent metadata providers.
4. Normalized artist/title/album information.
5. Duration as supporting evidence.
6. Version markers such as `Live`, `Acoustic`, `Remix`, `Demo`, `Radio Edit`, or `Remastered`.
7. Fuzzy matching only as a supporting signal.

The resolver records a confidence level and supporting evidence. Ambiguous cases should be reviewable rather than silently creating a bad archive entry.

### File hashes are for integrity

SHA-256 answers **“Is this exactly the same file?”** It does not reliably answer **“Is this the same musical recording?”**

A FLAC and an MP3 can represent the same recording while having completely different hashes.

## Download lifecycle

A file becomes part of the archive only after it passes validation:

```text
Source item
    ↓
Resolve identity
    ↓
Download to temporary path
    ↓
Extract / convert if required
    ↓
Collect metadata + artwork
    ↓
Write tags
    ↓
Validate audio + metadata + artwork
    ↓
Calculate SHA-256
    ↓
Atomically move into music_files/
    ↓
Commit archive state to SQLite
```

This prevents half-written files, broken artwork, and failed downloads from being mistaken for completed archive entries.

## Metadata policy

Metadata should be **useful, lightweight, and evidence-based**.

Typical fields include:

- Title
- Artist
- Album
- Album artist
- Track number
- Disc number
- Year/date
- Genre
- ISRC
- Composer/performer information when useful
- Source/provenance information where appropriate
- Embedded cover art

The system should prefer reliable source/provider information over weak guesses.

## Artwork policy

Artwork is validated before it is embedded. The pipeline should reject:

- HTML error pages saved with an image extension.
- Corrupt image payloads.
- Undecodable image data.
- Obviously invalid dimensions.
- Broken placeholders when a valid artwork policy is required.

A missing artwork result is preferable to embedding broken artwork.

## Playlists

Playlists are **relationships, not file containers**.

The same archived track can appear in multiple playlists. Removing a track from an upstream playlist must not delete the corresponding archive file.

```text
Provider playlist
      │
      ├── new source item ──→ resolve ──→ archive if needed
      │
      ├── known source item ─→ reuse existing identity/file
      │
      └── removed item ──────→ keep archive; update relationship
```

## Synchronization and delivery

### rsync / SSH

The durable archive can be synchronized to another machine using `rsync` over SSH. The default philosophy is additive and conservative: synchronization should not unexpectedly delete music from the destination.

### Telegram

Telegram is an optional delivery mechanism. A delivery failure must not make an otherwise valid archive file invalid, and a successful archive should not need to be downloaded again merely because Telegram delivery failed.

## Resource target

The initial design targets a small host:

- **RAM:** ~1 GB
- **CPU:** 2 cores
- **Database:** SQLite
- **Deployment:** Docker Compose
- **Concurrency:** bounded
- **Media:** streamed rather than loaded into memory

The project intentionally avoids a heavyweight database or unnecessary always-on services.

## Planned technology stack

| Area | Technology | Role |
| --- | --- | --- |
| Runtime | Python | Application and orchestration |
| Database | SQLite | Archive source of truth |
| Media acquisition | yt-dlp + provider adapters | Source downloads |
| Media processing | FFmpeg | Extraction/conversion |
| Metadata | Mutagen | Audio tagging |
| Metadata enrichment | MusicBrainz / trusted providers | Identity and metadata evidence |
| Artwork | Cover Art Archive / trusted sources | Cover lookup |
| Delivery | Telegram Bot API | Optional file delivery |
| Device sync | rsync + SSH | Bulk archive synchronization |
| Deployment | Docker Compose | Self-hosted runtime |
| CLI | Typer or argparse | Operations |
| Testing | pytest | Unit/integration/regression tests |

The exact provider set and implementation details are intentionally kept behind interfaces so the archive core does not become coupled to one service.

## Project status

**Current status: Foundation implementation in progress.**

The product requirements are documented in [`PRD.md`](./PRD.md). The first implementation slice establishes the Python package, runtime paths, SQLite foundation, domain models, identity normalization, storage primitives, provider/metadata/pipeline/delivery boundaries, CLI, tests, and Docker scaffolding.

### Planned phases

- [x] Foundation: repository structure, configuration, SQLite schema, logging, CLI skeleton
- [ ] Single-source download pipeline
- [ ] Metadata tagging and validation
- [ ] Source identity + semantic deduplication
- [ ] Multi-provider identity resolution
- [ ] Artwork enrichment and validation
- [ ] Playlist synchronization
- [ ] Telegram delivery
- [ ] rsync/SSH synchronization
- [ ] Crash recovery and operational hardening
- [ ] Resource/performance tuning

## Target repository structure

```text
.
├── src/
│   └── music_downloader/
│       ├── cli.py
│       ├── config.py
│       ├── db.py
│       ├── models.py
│       ├── identity.py
│       ├── storage.py
│       ├── providers/
│       ├── metadata/
│       ├── pipeline/
│       └── delivery/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── PRD.md
├── README.md
└── README_DEV.md
```

The structure is intentionally modular. Provider-specific code should not leak into archive, identity, or persistence logic.

## Design invariants

The implementation should preserve these rules:

- Never publish an unvalidated audio file.
- Never embed known-broken artwork.
- Never use file hash as the sole musical identity.
- Never silently collapse meaningful recording variants.
- Never overwrite an existing archive file because of a naming collision.
- Never delete archive content merely because an upstream playlist changed.
- Never commit credentials or provider secrets.
- Never make cache data a prerequisite for archive correctness.
- Prefer deterministic decisions over opaque heuristics.

## Documentation

- **[Product Requirements Document](./PRD.md)** — complete product, architecture, data model, operational, and implementation requirements.
- **[Development Guide](./README_DEV.md)** — local setup, test/lint commands, and package boundaries.

## Contributing

This is currently a personal/self-hosted project. Contributions and implementation ideas should follow the requirements in `PRD.md`, especially around identity correctness, data safety, and low-resource operation.

When adding a new source/provider, keep provider-specific logic isolated behind an adapter so the archive and identity layers remain provider-agnostic.

## License

No license has been selected yet. Until one is added to the repository, treat the project as **all rights reserved**.
