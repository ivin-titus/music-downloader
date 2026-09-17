from pathlib import Path

import pytest

from music_downloader.db import connect, initialize
from music_downloader.models import ResolvedTrack, SourceTrack
from music_downloader.repository import ArchiveRepository
from music_downloader.state import TrackStatus


def repository(tmp_path: Path) -> ArchiveRepository:
    database = tmp_path / "archive.db"
    initialize(database)
    return ArchiveRepository(connect(database))


def test_transaction_commits_a_complete_unit_of_work(tmp_path: Path) -> None:
    repo = repository(tmp_path)

    with repo.transaction():
        track_id = repo.create_track(ResolvedTrack(title="Example", artist="Artist"))
        repo.upsert_source(
            SourceTrack(provider="test", source_id="1", title="Example"),
            track_id=track_id,
        )

    row = repo.get_track(track_id)
    source = repo.connection.execute(
        "SELECT track_id FROM sources WHERE provider = 'test' AND source_id = '1'"
    ).fetchone()

    assert row["title"] == "Example"
    assert source["track_id"] == track_id
    repo.close()


def test_transaction_rolls_back_all_changes_on_failure(tmp_path: Path) -> None:
    repo = repository(tmp_path)

    with pytest.raises(RuntimeError):
        with repo.transaction():
            repo.create_track(ResolvedTrack(title="Should Roll Back"))
            raise RuntimeError("abort")

    assert repo.connection.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 0
    repo.close()


def test_source_upsert_preserves_existing_track_link(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    track_id = repo.create_track(ResolvedTrack(title="Example"))

    with repo.transaction():
        repo.upsert_source(
            SourceTrack(provider="test", source_id="1", title="Example"),
            track_id=track_id,
        )
        repo.upsert_source(
            SourceTrack(provider="test", source_id="1", title="Updated"),
        )

    source = repo.connection.execute(
        "SELECT source_title, track_id FROM sources WHERE provider = 'test' AND source_id = '1'"
    ).fetchone()
    assert source["source_title"] == "Updated"
    assert source["track_id"] == track_id
    repo.close()


def test_record_archive_rejects_unknown_track(tmp_path: Path) -> None:
    repo = repository(tmp_path)

    with pytest.raises(KeyError):
        repo.record_archive(999, "music/example.flac", "abc")

    repo.close()


def test_status_transition_is_persisted(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    track_id = repo.create_track(ResolvedTrack(title="Example"))

    with repo.transaction():
        repo.set_track_status(track_id, TrackStatus.RESOLVING)

    assert repo.get_track(track_id)["status"] == TrackStatus.RESOLVING.value
    repo.close()
