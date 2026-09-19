from __future__ import annotations
import tempfile
from pathlib import Path
from music_downloader.identity import resolve_source_track
from music_downloader.models import SourceTrack
from music_downloader.repository import ArchiveRepository
from music_downloader.state import TrackStatus
from music_downloader.storage import atomic_move,sha256_file
from music_downloader.metadata.audio import tag_mp3,validate_audio
from music_downloader.providers.base import Provider

class ArchiveService:
    def __init__(self,repository:ArchiveRepository,provider:Provider,music_root:Path)->None:
        self.repository=repository; self.provider=provider; self.music_root=music_root
    def ingest(self,source:SourceTrack)->int:
        resolved=resolve_source_track(source)
        with self.repository.transaction():
            source_id=self.repository.upsert_source(source)
            row=self.repository.connection.execute("SELECT track_id FROM sources WHERE id=?",(source_id,)).fetchone()
            track_id=row["track_id"] if row else None
            if track_id is None:
                track_id=self.repository.create_track(resolved)
                self.repository.upsert_source(source,track_id=track_id)
            current=TrackStatus(self.repository.get_track(track_id)["status"])
            if current==TrackStatus.ARCHIVED:
                return track_id
            if current==TrackStatus.DISCOVERED: self.repository.set_track_status(track_id,TrackStatus.RESOLVING)
        final=self.music_root/self._filename(resolved.title,resolved.artist)
        if final.exists():
            digest=sha256_file(final)
            with self.repository.transaction():
                current=TrackStatus(self.repository.get_track(track_id)["status"])
                if current!=TrackStatus.ARCHIVED:
                    for target in (TrackStatus.DOWNLOADING,TrackStatus.PROCESSING,TrackStatus.VALIDATING):
                        self.repository.set_track_status(track_id,target)
                self.repository.record_archive(track_id,str(final),digest)
            return track_id
        try:
            with self.repository.transaction(): self.repository.set_track_status(track_id,TrackStatus.DOWNLOADING)
            self.music_root.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.music_root) as temp_dir:
                temp=Path(temp_dir)/f"{track_id}.mp3"
                self.provider.download(source,str(temp))
                with self.repository.transaction(): self.repository.set_track_status(track_id,TrackStatus.PROCESSING)
                validate_audio(temp); tag_mp3(temp,resolved); validate_audio(temp)
                with self.repository.transaction(): self.repository.set_track_status(track_id,TrackStatus.VALIDATING)
                digest=sha256_file(temp); atomic_move(temp,final)
                with self.repository.transaction(): self.repository.record_archive(track_id,str(final),digest)
            return track_id
        except Exception as exc:
            with self.repository.transaction():
                current=TrackStatus(self.repository.get_track(track_id)["status"])
                if current not in (TrackStatus.FAILED,TrackStatus.ARCHIVED): self.repository.set_track_status(track_id,TrackStatus.FAILED)
            raise RuntimeError(f"ingest failed for source {source.source_id}: {exc}") from exc
    @staticmethod
    def _filename(title:str,artist:str|None)->str:
        stem=f"{artist} - {title}" if artist else title
        cleaned="".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in stem)
        cleaned=" ".join(cleaned.split()).strip(". ")
        return (cleaned or "untitled")+".mp3"
