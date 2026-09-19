from __future__ import annotations
import json, sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from typing import Iterator
from music_downloader.identity import identity_score, resolve_source_track
from music_downloader.models import ResolvedTrack, SourceTrack
from music_downloader.state import TrackStatus, require_transition

class ArchiveRepository:
    """Transactional persistence boundary for durable archive state."""
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection=connection; self._savepoint_counter=0
    @contextmanager
    def transaction(self)->Iterator[sqlite3.Connection]:
        if not self.connection.in_transaction:
            try: yield self.connection
            except BaseException: self.connection.rollback(); raise
            else: self.connection.commit()
            return
        self._savepoint_counter+=1; savepoint=f"archive_repository_{self._savepoint_counter}"
        self.connection.execute(f"SAVEPOINT {savepoint}")
        try: yield self.connection
        except BaseException:
            self.connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise
        else: self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
    def create_track(self,track:ResolvedTrack)->int:
        return int(self.connection.execute(
            "INSERT INTO tracks(title,artist,album,album_artist,duration_ms,recording_key,status) VALUES(?,?,?,?,?,?,?) RETURNING id",
            (track.title,track.artist,track.album,track.album_artist,track.duration_ms,track.recording_key,TrackStatus.DISCOVERED.value)
        ).fetchone()["id"])
    def get_track(self,track_id:int)->sqlite3.Row:
        row=self.connection.execute("SELECT * FROM tracks WHERE id=?",(track_id,)).fetchone()
        if row is None: raise KeyError(f"unknown track id: {track_id}")
        return row
    def find_matching_track(self,source:SourceTrack,min_score:float=0.75)->int|None:
        resolved=resolve_source_track(source)
        rows=self.connection.execute("SELECT * FROM tracks WHERE status <> 'failed'").fetchall()
        best_id=None; best=0.0
        for row in rows:
            candidate=ResolvedTrack(row["title"],row["artist"],row["album"],row["album_artist"],row["duration_ms"],row["recording_key"])
            score=identity_score(source,candidate)
            if score>best: best=score; best_id=int(row["id"])
        return best_id if best>=min_score else None
    def upsert_source(self,track:SourceTrack,track_id:int|None=None)->int:
        payload=json.dumps(asdict(track),ensure_ascii=False,sort_keys=True)
        row=self.connection.execute(
            """INSERT INTO sources(provider,source_id,source_url,source_title,metadata_json,track_id)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(provider,source_id) DO UPDATE SET
               source_url=excluded.source_url,source_title=excluded.source_title,
               metadata_json=excluded.metadata_json,track_id=COALESCE(excluded.track_id,sources.track_id)
               RETURNING id""",
            (track.provider,track.source_id,track.url,track.title,payload,track_id)
        ).fetchone()
        return int(row["id"])
    def upsert_playlist(self,provider:str,source_id:str,title:str,url:str|None=None)->int:
        row=self.connection.execute(
            """INSERT INTO playlists(provider,source_id,title,source_url) VALUES(?,?,?,?)
               ON CONFLICT(provider,source_id) DO UPDATE SET title=excluded.title,source_url=excluded.source_url,updated_at=CURRENT_TIMESTAMP
               RETURNING id""",(provider,source_id,title,url)).fetchone()
        return int(row["id"])
    def replace_playlist_tracks(self,playlist_id:int,track_ids:list[int])->None:
        with self.transaction():
            self.connection.execute("DELETE FROM playlist_tracks WHERE playlist_id=?",(playlist_id,))
            self.connection.executemany(
                "INSERT INTO playlist_tracks(playlist_id,track_id,position) VALUES(?,?,?)",
                [(playlist_id,track_id,position) for position,track_id in enumerate(track_ids)]
            )
    def set_track_status(self,track_id:int,target:TrackStatus)->None:
        current=TrackStatus(self.get_track(track_id)["status"]); require_transition(current,target)
        self.connection.execute("UPDATE tracks SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(target.value,track_id))
    def record_archive(self,track_id:int,file_path:str,sha256:str)->None:
        self.get_track(track_id)
        self.connection.execute(
            "UPDATE tracks SET file_path=?,file_sha256=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (file_path,sha256,TrackStatus.ARCHIVED.value,track_id))
    def commit(self)->None: self.connection.commit()
    def rollback(self)->None: self.connection.rollback()
    def close(self)->None: self.connection.close()
