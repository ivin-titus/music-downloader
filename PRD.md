# Music Downloader — Product Requirements Document

## 1. Product Overview

Music Downloader is a lightweight, self-hosted personal music archive and playlist synchronizer. It ingests music from one or more supported sources, resolves the musical identity of each item using source titles plus corroborating metadata, downloads a high-quality audio file, writes validated lightweight metadata and cover art, stores durable archive state in SQLite, and exposes the archive for later synchronization or delivery.

The system is designed for a small always-on host with approximately 1 GB RAM and 2 CPU cores. It should be resumable, crash-safe, deterministic, and conservative about metadata: a file should never be published with obviously broken artwork or metadata.

## 2. Goals

- Maintain a durable personal music archive on disk.
- Support multiple source types/providers and use them together when resolving track identity.
- Treat the original source title/filename as the highest-priority filename signal.
- Compare metadata from multiple sides/providers when there is a conflict or ambiguity.
- Deduplicate semantically rather than relying on file hashes alone.
- Preserve source identity separately from musical identity.
- Keep SQLite as the source of truth for archive state.
- Keep actual audio files in a simple, portable directory tree.
- Write useful, lightweight audio metadata including cover art.
- Validate artwork and metadata before a downloaded file becomes part of the archive.
- Make playlist synchronization additive and safe.
- Support Telegram delivery without coupling delivery success to archive correctness.
- Support rsync over SSH as the primary bulk-device synchronization mechanism.
- Operate comfortably within low-resource limits.

## 3. Non-Goals

- Building a general-purpose streaming service.
- Re-encoding audio unnecessarily.
- Replacing dedicated music players/library applications.
- Perfectly identifying every obscure recording automatically.
- Maintaining an online multi-user service.
- Treating a cryptographic file hash as musical identity.
- Keeping an unlimited permanent cache of provider responses or temporary media.

## 4. Core Principles

1. **SQLite knows what the archive contains.**
2. **The filesystem contains the archive.**
3. **Playlists describe relationships to tracks; they do not own files.**
4. **Source identity and musical identity are different concepts.**
5. **Identity resolution decides whether two sources represent the same musical recording.**
6. **A source title is the strongest filename signal, but metadata corroboration determines identity.**
7. **Synchronization is additive by default and must not silently delete archive content.**
8. **Downloaded files become visible to the archive only after validation succeeds.**
9. **Temporary work is disposable and recoverable.**
10. **Determinism is preferred over cleverness.**

## 5. Storage Layout

The host directory should be:

```text
~/music_downloader/
├── app_data/
│   ├── music_downloader.db
│   ├── cache/
│   ├── logs/
│   └── state/
├── music_files/
│   └── ... actual audio archive ...
├── docker-compose.yml
├── Dockerfile
└── code/
    └── ... application source ...
```

`music_files/` is the durable archive and should be easy to back up or mount into another application. `app_data/` contains database, cache, logs, and operational state. Cache contents must be safe to delete and recreate.

A reasonable archive layout is:

```text
music_files/
└── Artist/
    └── Album/
        └── Track.ext
```

The exact directory scheme may evolve, but it must be deterministic, portable, filesystem-safe, and independent of transient source URLs.

## 6. Source Identity vs Musical Identity

Every imported item has a **source identity** and may resolve to a **musical identity**.

Examples of source identity:

- YouTube video ID
- Source playlist ID + item ID
- Provider track ID
- URL

Source identity is unique to a provider and must prevent repeated downloading of the same source item.

Musical identity represents the actual track/recording. Multiple source items can map to the same musical identity.

This distinction is essential because:

- Different providers can point to the same recording.
- The same song can have studio, live, acoustic, remix, remaster, or edit variants.
- A provider may change its title while the underlying recording remains the same.
- Two source files may have different encodings but represent the same recording.

## 7. Playlist Management

The application must support multiple playlists.

A playlist contains ordered playlist items. A playlist item references a source item and, once resolved, a musical track.

Required behavior:

- Import/synchronize a playlist from a supported source.
- Preserve playlist ordering.
- Detect newly added source items.
- Detect source items that were already archived.
- Avoid re-downloading known source identities.
- Keep playlist relationships even when the same track appears in multiple playlists.
- Record enough source information to re-sync later.
- Do not delete an archive track merely because it disappeared from a source playlist.

## 8. Multi-Source Track Identity Resolution

Identity resolution is the central correctness feature.

### 8.1 Inputs

Use available evidence from:

- Original source title.
- Provider/source metadata.
- Artist.
- Album.
- Album artist.
- Track number.
- Disc number.
- Duration.
- ISRC, when available.
- Provider IDs.
- Release information.
- Existing archive metadata.
- External trusted metadata providers.
- Audio/container metadata when importing existing files.

### 8.2 Priority

1. Exact provider/source identity match.
2. Strong identifiers such as ISRC where trustworthy.
3. Agreement across independent metadata providers.
4. Normalized artist + title + album/release information.
5. Duration as supporting evidence, not sole identity.
6. Fuzzy title matching only as a supporting signal.

The original source title remains the primary naming signal for the resulting filename unless a stronger deterministic normalization rule is required for safety.

### 8.3 Conflict Handling

When providers disagree:

- Do not blindly select the first response.
- Normalize comparable fields.
- Compare independent evidence.
- Detect common title suffixes such as `Official Video`, `Lyrics`, `Audio`, `Remastered`, `Live`, `Acoustic`, `Remix`, etc., without erasing meaningful version information.
- Prefer exact identifiers over fuzzy text matches.
- Require higher confidence when variant information conflicts.
- Mark unresolved/ambiguous items for manual review rather than creating a likely-wrong archive entry.

### 8.4 Confidence

Identity resolution should produce a confidence level and an explanation/evidence set.

Suggested levels:

- **Exact** — authoritative identifier or exact known source identity.
- **High** — multiple independent metadata signals agree.
- **Medium** — strong textual/duration evidence but limited corroboration.
- **Low** — conflicting or incomplete evidence.
- **Unknown** — insufficient information.

Automatic archive insertion should require an appropriate minimum confidence threshold. Low-confidence cases should remain reviewable and must not silently create incorrect duplicates.

## 9. Version / Recording Awareness

The system must distinguish meaningful recording variants where evidence supports it.

Examples:

- Studio vs live.
- Acoustic vs original.
- Remix vs original.
- Radio edit vs album version.
- Extended mix.
- Remaster.
- Demo.
- Instrumental.
- Explicit/clean version when the recording differs.

Do not collapse variants solely because artist and title are similar.

Conversely, cosmetic provider suffixes must not cause unnecessary duplicates.

## 10. Deduplication

Deduplication must operate at multiple levels.

### 10.1 Source-Level Deduplication

A source/provider ID or canonical source URL should be unique where possible.

### 10.2 Musical-Level Deduplication

Compare candidate tracks using:

- Strong IDs such as ISRC.
- Normalized artist/title.
- Album/release.
- Duration.
- Version/remix/live markers.
- Cross-provider agreement.
- Existing archive metadata.

### 10.3 File Hash

SHA-256 or another cryptographic hash is used for file integrity and exact-byte detection. It is **not** the primary musical identity mechanism.

Two differently encoded files can be the same recording, and the same recording may legitimately exist at different bitrates or containers.

## 11. Filename Resolution

Filename resolution must prioritize the actual source title/filename.

Requirements:

- Preserve Unicode.
- Preserve emojis when supported by the filesystem.
- Preserve meaningful punctuation.
- Sanitize only characters that are unsafe on the target filesystem.
- Avoid excessive normalization that changes the visible title.
- Prevent path traversal.
- Apply deterministic collision handling.

If two different files resolve to the same path, use deterministic disambiguation rather than overwriting an existing archive file.

The filename should generally be based on the source title, while embedded metadata should contain normalized musical metadata.

## 12. Metadata Enrichment

Every published music file should contain useful metadata while remaining lightweight.

Preferred fields include:

- Title.
- Artist.
- Album.
- Album artist.
- Track number.
- Disc number where applicable.
- Date/year where reliable.
- Genre where reliable.
- ISRC where available.
- Composer/performer fields when available and useful.
- Comment/source provenance when appropriate.
- Embedded cover art.

Metadata should be sourced from the best available evidence and must not overwrite reliable source information with weak guesses.

## 13. Artwork

Artwork is part of the published file, not an optional afterthought.

Requirements:

- Prefer authoritative or trusted artwork sources.
- Validate that the downloaded payload is actually an image.
- Reject HTML/error pages masquerading as image files.
- Validate image dimensions and decodability.
- Avoid embedding obviously broken/corrupt artwork.
- Prefer sensible album/release artwork over arbitrary thumbnails when available.
- Keep artwork size reasonable for a lightweight archive.
- Embed artwork in the audio file when the container/tag format supports it.

If valid artwork cannot be obtained, the application may publish the audio without artwork only if the configured policy allows it; it must never embed a broken placeholder payload.

## 14. Audio Download Pipeline

A download should be treated as a staged transaction:

```text
source item
   ↓
resolve identity
   ↓
download to temporary path
   ↓
extract/convert only when required
   ↓
collect metadata/artwork
   ↓
write tags
   ↓
validate audio + metadata + artwork
   ↓
compute integrity hash
   ↓
atomically move into archive
   ↓
commit SQLite archive state
```

Temporary files must not appear as valid archive entries.

Do not re-encode audio unless required by the configured output format. Prefer preserving the best available source quality within the project's supported format policy.

FFmpeg should handle media conversion/extraction where necessary. yt-dlp should handle supported web media acquisition.

## 15. Validation

Before a file is considered archived, validate:

### Audio

- File exists.
- File is readable.
- Container/codec is supported.
- Duration is plausible.
- File is not obviously truncated/corrupt.

### Metadata

- Required tags are present.
- Text is valid UTF-8/Unicode as applicable.
- Track and disc numbering are sane.
- Metadata does not contain provider error messages or garbage.

### Artwork

- Embedded image can be decoded.
- MIME/type is consistent.
- Dimensions are reasonable.
- No known error-page payload is embedded.

### Integrity

- Compute SHA-256 after the final file is written.
- Store size and hash in SQLite.

Only after validation should the file be atomically moved to its final path and marked available.

## 16. SQLite Data Model

SQLite is the source of truth for logical archive state.

### `playlists`

- `id`
- `provider`
- `source_playlist_id`
- `name`
- `source_url`
- `last_synced_at`
- `created_at`
- `updated_at`

Unique key: `(provider, source_playlist_id)`.

### `playlist_items`

- `id`
- `playlist_id`
- `source_item_id`
- `position`
- `source_url`
- `track_id` nullable
- `created_at`
- `updated_at`

Unique key: `(playlist_id, source_item_id)`.

### `tracks`

- `id`
- canonical title
- canonical artist
- canonical album
- album artist
- normalized identity fields
- version/variant information
- ISRC nullable
- duration nullable
- identity confidence
- identity explanation/evidence
- created_at
- updated_at

### `files`

- `id`
- `track_id`
- relative path
- format/container
- codec
- bitrate/sample rate/channels where useful
- duration
- size_bytes
- sha256
- status
- created_at
- updated_at

Unique path and/or integrity constraints should prevent accidental duplicate archive records.

### `track_metadata_sources`

- `id`
- `track_id`
- provider
- provider_track_id nullable
- source_url nullable
- observed title/artist/album/etc.
- raw/normalized evidence as appropriate
- confidence
- fetched_at

This table preserves provenance and allows identity decisions to be audited without retaining excessive raw provider data.

### `artwork`

- `id`
- `track_id`
- source/provider
- source URL or provider ID where appropriate
- mime type
- dimensions
- sha256
- local/cache reference if needed
- validation status
- created_at

### `download_jobs`

- `id`
- source/provider
- source item ID
- playlist item ID nullable
- track ID nullable
- state
- attempts
- last_error
- started_at
- completed_at
- created_at
- updated_at

### `telegram_deliveries`

- `id`
- file ID
- destination/chat identifier
- delivery state
- remote message identifier where applicable
- attempts
- last_error
- sent_at
- created_at
- updated_at

Telegram delivery is intentionally independent from archive state.

## 17. State Machine

A download job should use explicit states, for example:

```text
pending
  ↓
resolving
  ↓
resolved
  ↓
downloading
  ↓
processing
  ↓
validating
  ↓
archived
```

Failure paths should record an error and retain enough state for retry:

```text
pending → failed
resolving → failed
resolved → failed
 downloading → failed
processing → failed
validating → failed
```

A retry should resume safely without creating duplicate archive entries.

## 18. Crash Recovery

The application must tolerate interruption during:

- playlist sync
- metadata lookup
- download
- conversion
- tagging
- artwork retrieval
- validation
- filesystem move
- database commit

Use atomic filesystem operations and transactional database writes.

A restart should be able to inspect incomplete jobs and either safely resume or clean temporary state.

No half-written file should be presented as a completed archive item.

## 19. Telegram Delivery

Telegram is an optional delivery channel, not the archive itself.

Requirements:

- Send only files that have passed archive validation.
- Record delivery status independently.
- Retry transient failures.
- Do not re-download a file merely because Telegram delivery failed.
- Avoid duplicate sends where the previous delivery is known to have succeeded.
- Keep bot credentials outside source control.

## 20. Device Synchronization

`rsync` over SSH is the primary bulk synchronization mechanism.

Requirements:

- Sync from `music_files/` to a remote device/host.
- Preserve filenames, Unicode, timestamps as appropriate, and file contents.
- Prefer additive synchronization by default.
- Provide dry-run support.
- Verify integrity using file sizes and SHA-256 where required by the selected sync mode.
- Never delete remote music merely because it disappeared from a source playlist.

The SQLite database remains the authoritative inventory on the server.

## 21. Resource Constraints

Target baseline:

- 1 GB RAM.
- 2 CPU cores.
- Single-user deployment.
- SQLite instead of a heavyweight database.
- Minimal long-lived worker processes.

Design implications:

- Avoid loading large media files into memory.
- Stream downloads where possible.
- Keep provider responses compact.
- Use bounded concurrency.
- Make caches disposable and size-limited.
- Avoid unnecessary background services.
- Prefer external tools such as FFmpeg for media work while keeping worker orchestration lightweight.

## 22. Docker

The repository should provide a straightforward Docker deployment.

The container should mount:

```text
~/music_downloader/app_data:/app/app_data
~/music_downloader/music_files:/app/music_files
```

Source code and compose configuration live under the project directory. Secrets must be provided through environment variables or a secret mechanism and must never be committed.

## 23. CLI

A CLI should be the primary operational interface initially.

Example commands:

```text
music-downloader playlist sync <playlist>
music-downloader download <source>
music-downloader retry
music-downloader status
music-downloader verify
music-downloader dedupe
music-downloader sync <destination>
music-downloader telegram send <track-or-file>
music-downloader db check
```

Typer or argparse are suitable choices.

Commands should be safe by default, with explicit flags for destructive or unusual operations.

## 24. Error Handling and Logging

Errors should be categorized where useful:

- Source unavailable.
- Authentication/authorization failure.
- Metadata unavailable.
- Identity ambiguity.
- Download failure.
- Conversion failure.
- Invalid audio.
- Invalid artwork.
- Filesystem failure.
- Database failure.
- Telegram delivery failure.
- Remote synchronization failure.

Logs should be useful for diagnosis without dumping huge provider payloads or credentials.

Every failed job should retain a concise, actionable error message in SQLite.

## 25. Security

- Never commit API keys, cookies, bot tokens, SSH private keys, or credentials.
- Restrict filesystem permissions where practical.
- Sanitize all source-derived paths.
- Prevent path traversal.
- Treat downloaded metadata and artwork as untrusted input.
- Validate media before publishing it.
- Use SSH keys rather than passwords for automated rsync where possible.
- Keep the service local/self-hosted unless remote access is deliberately configured.

## 26. Recommended Technology Stack

- **Language:** Python.
- **Database:** SQLite.
- **Container:** Docker + Docker Compose.
- **Media acquisition:** yt-dlp and provider-specific adapters.
- **Media processing:** FFmpeg.
- **Tagging:** Mutagen.
- **Metadata:** MusicBrainz and other trusted providers, with provider-specific metadata as evidence.
- **Artwork:** Cover Art Archive and trusted provider artwork sources.
- **Optional enrichment:** Spotify/provider metadata when available and legally/technically appropriate.
- **Delivery:** Telegram Bot API.
- **Bulk sync:** rsync over SSH.
- **CLI:** Typer or argparse.
- **Tests:** pytest.

The implementation should keep provider integrations behind interfaces so that adding another source does not require rewriting the archive core.

## 27. Architecture

```text
                    ┌───────────────────────┐
                    │      CLI / API        │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Playlist / Jobs     │
                    │     Orchestrator      │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
      ┌───────▼───────┐ ┌──────▼──────┐ ┌───────▼────────┐
      │ Source Adapter │ │   Identity   │ │ Metadata / Art │
      │ / Downloader   │ │   Resolver   │ │   Enrichment   │
      └───────┬───────┘ └──────┬──────┘ └───────┬────────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
                     ┌─────────▼─────────┐
                     │ Validation /      │
                     │ Archive Pipeline  │
                     └─────────┬─────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
      ┌───────▼────────┐               ┌────────▼────────┐
      │     SQLite     │               │   music_files/  │
      │ source of truth│               │ durable archive │
      └────────────────┘               └────────┬────────┘
                                                │
                               ┌────────────────┼────────────────┐
                               │                │                │
                       ┌───────▼──────┐ ┌──────▼───────┐ ┌──────▼───────┐
                       │   Telegram   │ │ rsync / SSH  │ │ Backup /     │
                       │   Delivery   │ │  Sync        │ │ Other Tools  │
                       └──────────────┘ └──────────────┘ └──────────────┘
```

## 28. Testing Strategy

### Unit Tests

- Filename sanitization.
- Unicode/emoji handling.
- Metadata normalization.
- Variant detection.
- Identity scoring.
- Deduplication decisions.
- Collision handling.
- Artwork validation.
- State transitions.
- Retry behavior.

### Integration Tests

- Source adapter → downloader → metadata → validator → archive.
- SQLite transactions and crash recovery.
- Multiple source items resolving to one track.
- Multiple playlists referencing one track.
- Telegram delivery retries.
- rsync dry-run/integration behavior where practical.

### Regression Fixtures

Maintain a small set of representative cases:

- Exact duplicate source.
- Same song from two providers with slightly different titles.
- Live vs studio recording.
- Remix vs original.
- Remaster.
- Emoji-containing title.
- Unicode artist/title.
- Broken artwork URL returning HTML.
- Missing artwork.
- Provider metadata conflict.
- Interrupted download.
- Existing archive filename collision.

## 29. Operational Requirements

- Startup should validate database schema and required directories.
- `verify` should detect database/filesystem inconsistencies.
- A missing archive file referenced by SQLite should be reported as an integrity error.
- An untracked audio file may be reported for optional import/reconciliation.
- Database writes should use transactions.
- Temporary files should be cleaned periodically.
- Logs should have bounded retention.
- Cache cleanup must never delete durable archive content.

## 30. Phased Implementation

### Phase 1 — Foundation

- Repository structure.
- Docker/Compose.
- SQLite schema and migrations.
- Configuration.
- CLI skeleton.
- Filesystem abstraction.
- Logging.

### Phase 2 — Single Source Download

- First source adapter.
- yt-dlp integration.
- FFmpeg integration.
- Temporary download pipeline.
- Basic Mutagen tagging.
- File validation.
- Atomic archive move.

### Phase 3 — Identity and Deduplication

- Source identity records.
- Normalization utilities.
- Multi-source metadata model.
- Identity scoring.
- Semantic deduplication.
- Variant awareness.
- Provenance tracking.

### Phase 4 — Artwork and Enrichment

- Trusted metadata provider integration.
- Artwork lookup.
- Image validation.
- Cover embedding.
- Metadata quality checks.

### Phase 5 — Playlists

- Playlist import.
- Incremental playlist sync.
- Ordered playlist items.
- Multiple playlists sharing tracks.
- Safe retries.

### Phase 6 — Delivery and Sync

- Telegram delivery.
- rsync/SSH sync.
- Integrity verification.
- Operational commands.

### Phase 7 — Hardening

- Crash recovery.
- Extensive regression fixtures.
- Resource tuning.
- Observability improvements.
- Backup/restore documentation.
- Security review.

## 31. Definition of Done

The initial production-ready version is complete when it can:

1. Import a supported playlist/source.
2. Resolve source items into musical identities with explainable confidence.
3. Avoid duplicate downloads for repeated source items.
4. Recognize the same recording across multiple sources when evidence supports it.
5. Keep meaningful variants separate.
6. Download and process audio without exposing partial files.
7. Preserve a source-derived, Unicode-safe filename.
8. Write lightweight, useful metadata.
9. Embed only validated artwork.
10. Record provenance and integrity information in SQLite.
11. Recover safely from interrupted jobs.
12. Keep playlist relationships independent of archive file ownership.
13. Deliver archived files to Telegram without corrupting archive state when delivery fails.
14. Synchronize the durable archive over rsync/SSH.
15. Run reliably within approximately 1 GB RAM and 2 CPU cores.

## 32. Future Extensions

Potential future work, only after the core archive is reliable:

- Web UI.
- Additional source adapters.
- Automatic manual-review queue.
- Advanced acoustic fingerprinting as a secondary identity signal.
- More sophisticated release/edition modeling.
- Incremental backups.
- Read-only APIs for external music players.
- Search/indexing optimized for large personal archives.

These extensions must not compromise the core properties of correctness, portability, low resource usage, and recoverability.

## 33. Guiding Principle

> **SQLite knows what the archive contains; the filesystem contains the archive; playlists only describe relationships to tracks; synchronization is additive; and identity resolution decides whether two sources really represent the same recording.**
