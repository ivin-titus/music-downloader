from pathlib import Path

from typer.testing import CliRunner

from music_downloader.cli import app
from music_downloader.db import connect, initialize
from music_downloader.repository import ArchiveRepository
from music_downloader.state import TrackStatus

runner = CliRunner()


def test_status_reports_tracks_and_jobs(tmp_path: Path):
    initialize(tmp_path / "db.sqlite")
    connection = connect(tmp_path / "db.sqlite")
    repository = ArchiveRepository(connection)
    repository.connection.execute(
        "INSERT INTO tracks(title,status) VALUES(?,?)",
        ("Track", TrackStatus.ARCHIVED.value),
    )
    repository.connection.execute(
        "INSERT INTO jobs(idempotency_key,kind,state) VALUES(?,?,?)",
        ("fake:item", "ingest", "pending"),
    )
    connection.commit()

    result = runner.invoke(app, ["status", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "archived: 1" in result.stdout
    assert "pending: 1" in result.stdout


def test_retry_reports_missing_source_metadata_as_failure(tmp_path: Path, monkeypatch):
    initialize(tmp_path / "db.sqlite")
    connection = connect(tmp_path / "db.sqlite")
    repository = ArchiveRepository(connection)
    repository.connection.execute(
        "INSERT INTO jobs(idempotency_key,kind,state) VALUES(?,?,?)",
        ("fake:missing", "ingest", "pending"),
    )
    connection.commit()
    monkeypatch.setattr("music_downloader.cli.YtDlpProvider", lambda: object())

    result = runner.invoke(app, ["retry", "--root", str(tmp_path)])

    assert result.exit_code == 1
    assert "source metadata is unavailable" in result.stderr


def test_playlist_downloads_into_requested_output_directory(tmp_path: Path, monkeypatch):
    from music_downloader.models import SourceTrack
    from music_downloader.providers.base import ProviderItem

    class FakeProvider:
        name = "fake"

        def inspect(self, url):
            raise NotImplementedError

        def playlist(self, url):
            yield ProviderItem(
                SourceTrack("fake", "item-1", "Outside", artist="Artist"),
                "playlist-1",
                "Playlist",
                url,
            )

        def download(self, source, destination):
            Path(destination).write_bytes(b"audio")

    monkeypatch.setattr("music_downloader.cli.YtDlpProvider", FakeProvider)
    monkeypatch.setattr("music_downloader.pipeline.archive.validate_audio", lambda path: None)
    monkeypatch.setattr("music_downloader.pipeline.archive.tag_mp3", lambda *args, **kwargs: None)

    archive_root = tmp_path / "archive"
    output = tmp_path / "phone-ready" / "playlist-a"
    result = runner.invoke(
        app,
        [
            "playlist",
            "https://example.test/playlist",
            "--root",
            str(archive_root),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert (output / "Artist - Outside.mp3").exists()
    assert str(output) in result.stdout
