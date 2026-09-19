from __future__ import annotations

import sqlite3
from collections.abc import Iterable

Migration = tuple[int, tuple[str, ...]]

MIGRATIONS: tuple[Migration, ...] = (
    (1, (
        """CREATE TABLE IF NOT EXISTS tracks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, artist TEXT, album TEXT, album_artist TEXT, duration_ms INTEGER, year INTEGER, recording_key TEXT, status TEXT NOT NULL DEFAULT 'discovered', file_path TEXT, file_sha256 TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS sources (id INTEGER PRIMARY KEY, provider TEXT NOT NULL, source_id TEXT NOT NULL, source_url TEXT, source_title TEXT, metadata_json TEXT, track_id INTEGER REFERENCES tracks(id) ON DELETE SET NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(provider, source_id))""",
        """CREATE TABLE IF NOT EXISTS playlists (id INTEGER PRIMARY KEY, provider TEXT NOT NULL, source_id TEXT NOT NULL, title TEXT NOT NULL, source_url TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(provider, source_id))""",
        """CREATE TABLE IF NOT EXISTS playlist_tracks (playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE, track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE, position INTEGER NOT NULL, PRIMARY KEY (playlist_id, track_id))""",
        "CREATE INDEX IF NOT EXISTS idx_sources_track_id ON sources(track_id)",
        "CREATE INDEX IF NOT EXISTS idx_tracks_recording_key ON tracks(recording_key)",
        "CREATE INDEX IF NOT EXISTS idx_tracks_status ON tracks(status)",
    )),
    (2, (
        """CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, track_id INTEGER REFERENCES tracks(id) ON DELETE CASCADE, state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3, last_error TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS artwork (id INTEGER PRIMARY KEY, track_id INTEGER NOT NULL UNIQUE REFERENCES tracks(id) ON DELETE CASCADE, mime_type TEXT NOT NULL, sha256 TEXT NOT NULL, data BLOB NOT NULL, width INTEGER, height INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
        "CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_track_id ON jobs(track_id)",
    )),
)

def _create_migration_table(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

def applied_versions(connection: sqlite3.Connection) -> set[int]:
    _create_migration_table(connection)
    return {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}

def migrate(connection: sqlite3.Connection, migrations: Iterable[Migration] = MIGRATIONS) -> None:
    _create_migration_table(connection)
    applied = applied_versions(connection)
    for version, statements in sorted(migrations, key=lambda item: item[0]):
        if version in applied:
            continue
        if any(existing > version for existing in applied):
            raise RuntimeError(f"cannot apply migration {version} after a newer migration")
        try:
            with connection:
                for statement in statements:
                    connection.execute(statement)
                connection.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        except sqlite3.IntegrityError as exc:
            raise RuntimeError(f"migration {version} failed to record") from exc
        applied.add(version)
