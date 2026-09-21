from pathlib import Path

import pytest

from music_downloader.db import connect, initialize
from music_downloader.jobs import JobRepository, JobState
from music_downloader.repository import ArchiveRepository


def repo(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    initialize(db)
    return connect(db)


def test_enqueue_is_idempotent_and_retry_budget_is_bounded(tmp_path: Path):
    connection = repo(tmp_path)
    jobs = JobRepository(ArchiveRepository(connection))
    first = jobs.enqueue(idempotency_key="track:abc", kind="download")
    assert jobs.enqueue(idempotency_key="track:abc", kind="download") == first
    assert jobs.claim(first).state == JobState.RUNNING
    assert jobs.fail(first, "network") == JobState.PENDING
    assert jobs.claim(first).attempts == 2
    assert jobs.fail(first, "network") == JobState.PENDING
    assert jobs.claim(first).attempts == 3
    assert jobs.fail(first, "network") == JobState.FAILED
    with pytest.raises(RuntimeError):
        jobs.claim(first)


def test_success_is_terminal(tmp_path: Path):
    connection = repo(tmp_path)
    jobs = JobRepository(ArchiveRepository(connection))
    job = jobs.enqueue(idempotency_key="x", kind="download")
    jobs.claim(job)
    jobs.succeed(job)
    assert jobs.get(job).state == JobState.SUCCEEDED
    assert jobs.get(job).attempts == 1
    assert jobs.get(job).completed_at is not None
    with pytest.raises(RuntimeError):
        jobs.succeed(job)


def test_claim_sets_lease_and_heartbeat_extends_it(tmp_path: Path):
    connection = repo(tmp_path)
    jobs = JobRepository(ArchiveRepository(connection))
    job = jobs.enqueue(idempotency_key="lease", kind="download")
    claimed = jobs.claim(job, lease_seconds=60)
    assert claimed.lease_until is not None
    refreshed = jobs.heartbeat(job, lease_seconds=120)
    assert refreshed.lease_until is not None
    assert refreshed.lease_until > claimed.lease_until


def test_stale_running_job_is_recovered(tmp_path: Path):
    connection = repo(tmp_path)
    jobs = JobRepository(ArchiveRepository(connection))
    job = jobs.enqueue(idempotency_key="stale", kind="download")
    jobs.claim(job, lease_seconds=60)
    connection.execute(
        "UPDATE jobs SET lease_until=datetime(CURRENT_TIMESTAMP, '-1 second') WHERE id=?",
        (job,),
    )
    connection.commit()
    assert jobs.recover_stale() == 1
    recovered = jobs.get(job)
    assert recovered.state == JobState.PENDING
    assert recovered.lease_until is None
    assert jobs.claim(job).attempts == 2


def test_claim_next_skips_exhausted_and_claims_pending(tmp_path: Path):
    connection = repo(tmp_path)
    jobs = JobRepository(ArchiveRepository(connection))
    exhausted = jobs.enqueue(idempotency_key="exhausted", kind="download", max_attempts=1)
    jobs.claim(exhausted)
    connection.execute(
        "UPDATE jobs SET lease_until=datetime(CURRENT_TIMESTAMP, '-1 second') WHERE id=?",
        (exhausted,),
    )
    pending = jobs.enqueue(idempotency_key="pending", kind="download")
    connection.commit()
    claimed = jobs.claim_next()
    assert claimed is not None
    assert claimed.id == pending
    assert jobs.get(exhausted).state == JobState.FAILED


def test_lease_must_be_positive(tmp_path: Path):
    connection = repo(tmp_path)
    jobs = JobRepository(ArchiveRepository(connection))
    job = jobs.enqueue(idempotency_key="bad-lease", kind="download")
    with pytest.raises(ValueError):
        jobs.claim(job, lease_seconds=0)
    with pytest.raises(ValueError):
        jobs.heartbeat(job, lease_seconds=0)
