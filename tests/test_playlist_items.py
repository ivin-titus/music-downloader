from music_downloader.db import connect, initialize
from music_downloader.models import SourceTrack
from music_downloader.pipeline.archive import ArchiveService
from music_downloader.pipeline.playlist import PlaylistService
from music_downloader.providers.base import ProviderItem
from music_downloader.repository import ArchiveRepository


class FakeProvider:
    name = "fake"

    def inspect(self, url):
        raise NotImplementedError

    def playlist(self, url):
        raise NotImplementedError

    def download(self, source, destination):
        with open(destination, "wb") as handle:
            handle.write(b"audio")


def test_playlist_items_preserve_source_identity_order_and_duplicate_tracks(tmp_path, monkeypatch):
    database = tmp_path / "db.sqlite"
    initialize(database)
    connection = connect(database)
    repository = ArchiveRepository(connection)
    monkeypatch.setattr("music_downloader.pipeline.archive.validate_audio", lambda path: None)
    monkeypatch.setattr("music_downloader.pipeline.archive.tag_mp3", lambda *args, **kwargs: None)

    archive = ArchiveService(repository, FakeProvider(), tmp_path / "music")
    first = SourceTrack("fake", "item-1", "Track", artist="Artist")
    second = SourceTrack("fake", "item-2", "Track", artist="Artist")
    items = [
        ProviderItem(first, "playlist-1", "Playlist", "https://example.test/p/1"),
        ProviderItem(second, "playlist-1", "Playlist", "https://example.test/p/1"),
    ]

    playlist_id = PlaylistService(repository, archive).sync(items)
    rows = connection.execute(
        """SELECT source_item_id,position,source_url,track_id
           FROM playlist_items WHERE playlist_id=? ORDER BY position""",
        (playlist_id,),
    ).fetchall()

    assert [row["source_item_id"] for row in rows] == ["item-1", "item-2"]
    assert [row["position"] for row in rows] == [0, 1]
    assert [row["source_url"] for row in rows] == [None, None]
    assert rows[0]["track_id"] == rows[1]["track_id"]
    assert connection.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 1
