from pathlib import Path
from music_downloader.db import connect, initialize
from music_downloader.models import SourceTrack
from music_downloader.pipeline.archive import ArchiveService
from music_downloader.repository import ArchiveRepository

class FakeProvider:
    name="fake"
    def inspect(self,url): raise NotImplementedError
    def playlist(self,url): raise NotImplementedError
    def download(self,source,destination):
        Path(destination).write_bytes(b"audio"*400)

def test_ingest_is_idempotent_for_same_recording(tmp_path,monkeypatch):
    database=tmp_path/"db.sqlite"; initialize(database)
    connection=connect(database)
    monkeypatch.setattr("music_downloader.pipeline.archive.validate_audio",lambda path:None)
    monkeypatch.setattr("music_downloader.pipeline.archive.tag_mp3",lambda path,track,artwork=None,mime_type="image/jpeg":None)
    service=ArchiveService(ArchiveRepository(connection),FakeProvider(),tmp_path/"music")
    source=SourceTrack("fake","abc","Song","https://example.test/song","Artist",duration_ms=180000)
    first=service.ingest(source)
    second=service.ingest(SourceTrack("other","xyz","song","https://example.test/other","artist",duration_ms=181000))
    assert first==second
    assert connection.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]==1
    assert connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]==2


def test_filename_preserves_source_title(monkeypatch, tmp_path):
    database = tmp_path / "db.sqlite"
    initialize(database)
    connection = connect(database)
    monkeypatch.setattr("music_downloader.pipeline.archive.validate_audio", lambda path: None)
    monkeypatch.setattr("music_downloader.pipeline.archive.tag_mp3", lambda path, track, artwork=None, mime_type="image/jpeg": None)
    monkeypatch.setattr(
        "music_downloader.pipeline.archive.resolve_source_track",
        lambda source: __import__("music_downloader.models", fromlist=["ResolvedTrack"]).ResolvedTrack(
            title="Canonical Title", artist="Artist"
        ),
    )
    service = ArchiveService(ArchiveRepository(connection), FakeProvider(), tmp_path / "music")
    source = SourceTrack("fake", "source-title", "Source Title [Live]", artist="Artist")
    track_id = service.ingest(source)
    row = connection.execute("SELECT file_path FROM tracks WHERE id=?", (track_id,)).fetchone()
    assert Path(row["file_path"]).name == "Artist - Source Title [Live].mp3"


def test_filename_collision_gets_deterministic_track_suffix(monkeypatch, tmp_path):
    database = tmp_path / "db.sqlite"
    initialize(database)
    connection = connect(database)
    music_root = tmp_path / "music"
    music_root.mkdir()
    existing = music_root / "Artist - Same Title.mp3"
    existing.write_bytes(b"untracked existing file")
    monkeypatch.setattr("music_downloader.pipeline.archive.validate_audio", lambda path: None)
    monkeypatch.setattr("music_downloader.pipeline.archive.tag_mp3", lambda path, track, artwork=None, mime_type="image/jpeg": None)
    service = ArchiveService(ArchiveRepository(connection), FakeProvider(), music_root)
    source = SourceTrack("fake", "collision", "Same Title", artist="Artist")
    track_id = service.ingest(source)
    row = connection.execute("SELECT file_path FROM tracks WHERE id=?", (track_id,)).fetchone()
    expected = music_root / f"Artist - Same Title [{track_id}].mp3"
    assert Path(row["file_path"]) == expected
    assert existing.read_bytes() == b"untracked existing file"
    assert expected.is_file()
