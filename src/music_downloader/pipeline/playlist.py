from __future__ import annotations

from collections.abc import Iterable

from music_downloader.pipeline.archive import ArchiveService
from music_downloader.providers.base import ProviderItem
from music_downloader.repository import ArchiveRepository


class PlaylistService:
    def __init__(self, repository: ArchiveRepository, archive: ArchiveService) -> None:
        self.repository = repository
        self.archive = archive

    def sync(self, items: Iterable[ProviderItem]) -> int | None:
        materialized = list(items)
        if not materialized:
            return None
        first = materialized[0]
        if not first.playlist_source_id:
            raise ValueError("provider items do not identify a playlist")

        playlist_id = self.repository.upsert_playlist(
            self.archive.provider.name,
            first.playlist_source_id,
            first.playlist_title or first.playlist_source_id,
            first.playlist_url,
        )
        track_ids = [self.archive.ingest(item.source) for item in materialized]
        self.repository.replace_playlist_items(playlist_id, materialized, track_ids)
        return playlist_id
