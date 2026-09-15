from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import Any

from music_downloader.models import SourceTrack
from music_downloader.state import TrackStatus, require_transition


class ArchiveRepository:
    """Small transactional repository over SQLite.

    Higher layers use this instead of issuing SQL directly. This keeps
    persistence policy in one place and makes crash/retry behavior explicit.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def upsert_source(self, track: SourceTrack) -> int:
        payload = json.dumps(asdict(track), ensure_ascii=False, sort_keys=True)
        cursor = self.connection.execute(
            """
            INSERT INTO sources (provider, source_id, source_url, source_title, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(provider, source_id) DO UPDATE SET
                source_url = excluded.source_url,
                source_title = excluded.source_title,
                metadata_json = excluded.metadata_json
            RETURNING id
            """,
            (track.provider, track.source_id, track.source_url, track.title, payload),
        )
        return int(cursor.fetchone()[0])

    def set_track_status(self, track_id: int, target: TrackStatus) -> None:
        row = self.connection.execute(
            "SELECT status FROM tracks WHERE id = ?", (track_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown track id: {track_id}")

        current = TrackStatus(row[0])
        require_transition(current, target)
        self.connection.execute(
            "UPDATE tracks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (target.value, track_id),
        )

    def record_archive(self, track_id: int, file_path: str, sha256: str) -> None:
        self.connection.execute(
            """
            UPDATE tracks
            SET file_path = ?, file_sha256 = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (file_path, sha256, TrackStatus.ARCHIVED.value, track_id),
        )

    def transaction(self):
        return self.connection

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()
