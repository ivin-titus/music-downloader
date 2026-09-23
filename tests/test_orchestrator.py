from pathlib import Path

from music_downloader.db import connect, initialize
from music_downloader.jobs import JobRepository, JobState
from music_downloader.models import SourceTrack
from music_downloader.pipeline.archive import ArchiveService
from music_downloader.repository import ArchiveRepository
from music_downloader.storage import sha256_file
from music_downloader.pipeline import DownloadOrchestrator


class FakeProvider:
    name = "fake"

    def inspect(self, url):
        raise NotImplementedError

    def playlist(self, url):
        raise NotImplementedError

    def download(self, source, destination):
        Path(destination).write_bytes(b"audio")


def test_ingest_is_persisted_as_a_succeeded_job(tmp_path, monkeypatch):
    database = tmp_path / "db.sqlite"
    initialize(database)
    connection = connect(database)
    repository = ArchiveRepository(connection)
    provider = FakeProvider()
    monkeypatch.setattr("music_downloader.pipeline.archive.validate_audio", lambda path: None)
    monkeypatch.setattr("music_downloader.pipeline.archive.tag_mp3", lambda *args, **kwargs: None)

    archive = ArchiveService(repository, provider, tmp_path / "music")
    source = SourceTrack("fake", "source-1", "Track", artist="Artist")
    orchestrator = DownloadOrchestrator(JobRepository(repository), archive)

    track_id = orchestrator.ingest(source)
    job = JobRepository(repository).get(1)

    assert job.state == JobState.SUCCEEDED
    assert job.track_id == track_id
    assert job.attempts == 1
    assert repository.get_track(track_id)["status"] == "archived"


def test_repeating_a_completed_ingest_is_idempotent(tmp_path, monkeypatch):
    database = tmp_path / "db.sqlite"
    initialize(database)
    connection = connect(database)
    repository = ArchiveRepository(connection)
    provider = FakeProvider()
    monkeypatch.setattr("music_downloader.pipeline.archive.validate_audio", lambda path: None)
    monkeypatch.setattr("music_downloader.pipeline.archive.tag_mp3", lambda *args, **kwargs: None)

    archive = ArchiveService(repository, provider, tmp_path / "music")
    source = SourceTrack("fake", "source-1", "Track", artist="Artist")
    orchestrator = DownloadOrchestrator(JobRepository(repository), archive)

    first = orchestrator.ingest(source)
    second = orchestrator.ingest(source)

    assert second == first
    assert repository.connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
    assert repository.connection.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 1


def test_failed_ingest_returns_job_to_pending(tmp_path, monkeypatch):
    database = tmp_path / "db.sqlite"
    initialize(database)
    connection = connect(database)
    repository = ArchiveRepository(connection)

    class FailingProvider(FakeProvider):
        def download(self, source, destination):
            raise RuntimeError("provider unavailable")

    archive = ArchiveService(repository, FailingProvider(), tmp_path / "music")
    orchestrator = DownloadOrchestrator(JobRepository(repository), archive)
    source = SourceTrack("fake", "source-fail", "Track")

    try:
        orchestrator.ingest(source)
    except RuntimeError:
        pass

    job = JobRepository(repository).get(1)
    assert job.state == JobState.PENDING
    assert job.attempts == 1
    assert "provider unavailable" in (job.last_error or "")
