from pathlib import Path
import pytest
from music_downloader.db import connect, initialize
from music_downloader.jobs import JobRepository, JobState
from music_downloader.repository import ArchiveRepository

def repo(tmp_path:Path):
    db=tmp_path/"db.sqlite"; initialize(db); return connect(db)

def test_enqueue_is_idempotent_and_retry_budget_is_bounded(tmp_path:Path):
    connection=repo(tmp_path); jobs=JobRepository(ArchiveRepository(connection))
    first=jobs.enqueue(idempotency_key="track:abc",kind="download")
    assert jobs.enqueue(idempotency_key="track:abc",kind="download")==first
    assert jobs.claim(first).state==JobState.RUNNING
    assert jobs.fail(first,"network") == JobState.PENDING
    assert jobs.claim(first).attempts==2
    assert jobs.fail(first,"network") == JobState.PENDING
    assert jobs.claim(first).attempts==3
    assert jobs.fail(first,"network") == JobState.FAILED
    with pytest.raises(RuntimeError): jobs.claim(first)

def test_success_is_terminal(tmp_path:Path):
    connection=repo(tmp_path); jobs=JobRepository(ArchiveRepository(connection))
    job=jobs.enqueue(idempotency_key="x",kind="download")
    jobs.claim(job); jobs.succeed(job)
    assert jobs.get(job).state==JobState.SUCCEEDED
    assert jobs.get(job).attempts==1
    with pytest.raises(RuntimeError): jobs.succeed(job)
