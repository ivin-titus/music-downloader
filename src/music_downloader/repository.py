from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from typing import Iterator

from music_downloader.models import ResolvedTrack, SourceTrack
from music_downloader.state import TrackStatus, require_transition


class ArchiveRepository:
    """Transactional persistence boundary for the durable archive state."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self._savepoint_counter = 0

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Commit an outer unit of work or isolate nested work with a savepoint."""
        if not self.connection.in_transaction:
            try:
                yield self.connection
            except BaseException:
                self.connection.rollback()
                raise
            else:
                self.connection.commit()
            return

        self._savepoint_counter += 1
        savepoint = f"archive_repository_{self._savepoint_counter}"
        self.connection.execute(f"SAVEPOINT {savepoint}")
        try:
            yield self.connection
        except BaseException:
            self.connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise
        else:
            self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")

    def create_track(self, track: ResolvedTrack) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO tracks (
                title, artist, album, album_artist, duration_ms, recording_key, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                track.title,
                track.artist,
                track.album,
                track.album_artist,
                track.duration_ms,
                track.recording_key,
                TrackStatus.DISCOVERED.value,
            ),
        )
        return int(cursor.fetchone()[0])

    def get_track(self, track_id: int) -> sqlite3.Row:
        row = self.connection.execute(
            "SELECT * FROM tracks WHERE id = ?", (track_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown track id: {track_id}")
        return row

    def upsert_source(self, track: SourceTrack, track_id: int | None = None) -> int:
        payload = json.dumps(asdict(track), ensure_ascii=False, sort_keys=True)
        cursor = self.connection.execute(
            """
            INSERT INTO sources (
                provider, source_id, source_url, source_title, metadata_json, track_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, source_id) DO UPDATE SET
                source_url = excluded.source_url,
                source_title = excluded.source_title,
                metadata_json = excluded.metadata_json,
                track_id = COALESCE(excluded.track_id, sources.track_id)
            RETURNING id
            """,
            (
                track.provider,
                track.source_id,
                track.source_url,
                track.title,
                payload,
                track_id,
            ),
        )
        return int(cursor.fetchone()[0])

    def set_track_status(self, track_id: int, target: TrackStatus) -> None:
        current = TrackStatus(self.get_track(track_id)["status"])
        require_transition(current, target)
        self.connection.execute(
            "UPDATE tracks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (target.value, track_id),
        )

    def record_archive(self, track_id: int, file_path: str, sha256: str) -> None:
        self.get_track(track_id)
        self.connection.execute(
            """
            UPDATE tracks
            SET file_path = ?, file_sha256 = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (file_path, sha256, TrackStatus.ARCHIVED.value, track_id),
        )

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()
