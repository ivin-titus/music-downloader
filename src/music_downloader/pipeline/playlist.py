from __future__ import annotations
from collections.abc import Iterable
from music_downloader.models import SourceTrack
from music_downloader.providers.base import ProviderItem
from music_downloader.repository import ArchiveRepository
from music_downloader.pipeline.archive import ArchiveService

class PlaylistService:
    def __init__(self,repository:ArchiveRepository,archive:ArchiveService)->None:
        self.repository=repository; self.archive=archive
    def sync(self,items:Iterable[ProviderItem])->int|None:
        materialized=list(items)
        if not materialized: return None
        first=materialized[0]
        if not first.playlist_source_id: raise ValueError("provider items do not identify a playlist")
        playlist_id=self.repository.upsert_playlist(
            self.archive.provider.name,first.playlist_source_id,
            first.playlist_title or first.playlist_source_id,first.playlist_url)
        track_ids=[]
        for item in materialized:
            track_ids.append(self.archive.ingest(item.source))
        self.repository.replace_playlist_tracks(playlist_id,track_ids)
        return playlist_id
