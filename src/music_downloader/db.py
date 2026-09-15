import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT,
    album TEXT,
    album_artist TEXT,
    duration_ms INTEGER,
    year INTEGER,
    recording_key TEXT,
    status TEXT NOT NULL DEFAULT 'discovered',
    file_path TEXT,
    file_sha256 TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_url TEXT,
    source_title TEXT,
    metadata_json TEXT,
    track_id INTEGER REFERENCES tracks(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, source_id)
);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, source_id)
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    PRIMARY KEY (playlist_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_sources_track_id ON sources(track_id);
CREATE INDEX IF NOT EXISTS idx_tracks_recording_key ON tracks(recording_key);
CREATE INDEX IF NOT EXISTS idx_tracks_status ON tracks(status);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize(path: Path) -> None:
    with connect(path) as connection:
        connection.executescript(SCHEMA)
