from __future__ import annotations

from music_downloader.jobs import JobRepository, JobState
from music_downloader.models import SourceTrack
from music_downloader.pipeline.archive import ArchiveService


class DownloadOrchestrator:
    """Run archive ingestion through the durable retryable job state machine."""

    def __init__(self, jobs: JobRepository, archive: ArchiveService) -> None:
        self.jobs = jobs
        self.archive = archive

    def ingest(self, source: SourceTrack, *, max_attempts: int = 3) -> int:
        job_id = self.jobs.enqueue(
            idempotency_key=f"{source.provider}:{source.source_id}",
            kind="ingest",
            max_attempts=max_attempts,
        )
        job = self.jobs.claim(job_id)
        if job.state == JobState.SUCCEEDED:
            if job.track_id is None:
                raise RuntimeError(f"completed ingest job {job.id} has no track id")
            return job.track_id

        try:
            track_id = self.archive.ingest(source)
            self.jobs.attach_track(job.id, track_id)
            self.jobs.succeed(job.id)
            return track_id
        except Exception as exc:
            self.jobs.fail(job.id, str(exc))
            raise
