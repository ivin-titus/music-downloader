from __future__ import annotations

from dataclasses import dataclass

from music_downloader.repository import ArchiveRepository


class JobState(str):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Job:
    id: int
    idempotency_key: str
    kind: str
    track_id: int | None
    state: str
    attempts: int
    max_attempts: int
    last_error: str | None
    started_at: str | None
    completed_at: str | None
    lease_until: str | None


class JobRepository:
    """Durable job primitives with lease-based crash recovery."""

    def __init__(self, archive: ArchiveRepository) -> None:
        self.archive = archive

    def enqueue(
        self,
        *,
        idempotency_key: str,
        kind: str,
        track_id: int | None = None,
        max_attempts: int = 3,
    ) -> int:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        with self.archive.transaction():
            row = self.archive.connection.execute(
                "SELECT id FROM jobs WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if row:
                return int(row["id"])
            row = self.archive.connection.execute(
                """INSERT INTO jobs(idempotency_key,kind,track_id,max_attempts)
                   VALUES(?,?,?,?) RETURNING id""",
                (idempotency_key, kind, track_id, max_attempts),
            ).fetchone()
            return int(row["id"])

    def claim(self, job_id: int, *, lease_seconds: int = 900) -> Job:
        self._validate_lease(lease_seconds)
        with self.archive.transaction():
            row = self.archive.connection.execute(
                "SELECT * FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown job id: {job_id}")
            if row["state"] == JobState.SUCCEEDED:
                return self._to_job(row)
            if row["state"] == JobState.RUNNING and not self._lease_expired(row["lease_until"]):
                raise RuntimeError(f"job {job_id} is already running")
            if row["attempts"] >= row["max_attempts"]:
                raise RuntimeError(f"job {job_id} exhausted its retry budget")
            self._mark_running(job_id, lease_seconds)
            return self._to_job(self._fetch(job_id))

    def claim_next(self, *, lease_seconds: int = 900) -> Job | None:
        self._validate_lease(lease_seconds)
        with self.archive.transaction():
            row = self.archive.connection.execute(
                """SELECT * FROM jobs
                   WHERE state=? OR (state=? AND lease_until IS NOT NULL AND lease_until <= CURRENT_TIMESTAMP)
                   ORDER BY id LIMIT 1""",
                (JobState.PENDING, JobState.RUNNING),
            ).fetchone()
            if row is None or row["attempts"] >= row["max_attempts"]:
                if row is not None and row["attempts"] >= row["max_attempts"]:
                    self.archive.connection.execute(
                        "UPDATE jobs SET state=?,completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (JobState.FAILED, row["id"]),
                    )
                return None
            self._mark_running(int(row["id"]), lease_seconds)
            return self._to_job(self._fetch(int(row["id"])))

    def heartbeat(self, job_id: int, *, lease_seconds: int = 900) -> Job:
        self._validate_lease(lease_seconds)
        with self.archive.transaction():
            row = self._fetch(job_id)
            if row["state"] != JobState.RUNNING:
                raise RuntimeError(f"job {job_id} is not running")
            self.archive.connection.execute(
                "UPDATE jobs SET lease_until=datetime(CURRENT_TIMESTAMP, ?),updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (f"+{lease_seconds} seconds", job_id),
            )
            return self._to_job(self._fetch(job_id))

    def recover_stale(self) -> int:
        """Return expired running jobs to pending, or fail exhausted jobs."""
        with self.archive.transaction():
            rows = self.archive.connection.execute(
                "SELECT id,attempts,max_attempts FROM jobs WHERE state=? AND lease_until IS NOT NULL AND lease_until <= CURRENT_TIMESTAMP",
                (JobState.RUNNING,),
            ).fetchall()
            for row in rows:
                if row["attempts"] >= row["max_attempts"]:
                    state = JobState.FAILED
                    completed = "CURRENT_TIMESTAMP"
                else:
                    state = JobState.PENDING
                    completed = "NULL"
                self.archive.connection.execute(
                    f"UPDATE jobs SET state=?,lease_until=NULL,completed_at={completed},updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (state, row["id"]),
                )
            return len(rows)

    def succeed(self, job_id: int) -> None:
        with self.archive.transaction():
            cur = self.archive.connection.execute(
                """UPDATE jobs SET state=?,last_error=NULL,lease_until=NULL,
                   completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND state=?""",
                (JobState.SUCCEEDED, job_id, JobState.RUNNING),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"job {job_id} is not running")

    def fail(self, job_id: int, error: str) -> str:
        if not error.strip():
            raise ValueError("error must not be empty")
        with self.archive.transaction():
            row = self.archive.connection.execute(
                "SELECT attempts,max_attempts,state FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown job id: {job_id}")
            if row["state"] != JobState.RUNNING:
                raise RuntimeError(f"job {job_id} is not running")
            state = JobState.PENDING if row["attempts"] < row["max_attempts"] else JobState.FAILED
            completed = "NULL" if state == JobState.PENDING else "CURRENT_TIMESTAMP"
            self.archive.connection.execute(
                f"UPDATE jobs SET state=?,last_error=?,lease_until=NULL,completed_at={completed},updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (state, error[:4000], job_id),
            )
            return state

    def get(self, job_id: int) -> Job:
        return self._to_job(self._fetch(job_id))

    def _fetch(self, job_id: int):
        row = self.archive.connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown job id: {job_id}")
        return row

    def _mark_running(self, job_id: int, lease_seconds: int) -> None:
        self.archive.connection.execute(
            """UPDATE jobs SET state=?,attempts=attempts+1,started_at=COALESCE(started_at,CURRENT_TIMESTAMP),
               lease_until=datetime(CURRENT_TIMESTAMP, ?),completed_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (f"+{lease_seconds} seconds", job_id),
        )

    @staticmethod
    def _validate_lease(lease_seconds: int) -> None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")

    @staticmethod
    def _lease_expired(lease_until: str | None) -> bool:
        if lease_until is None:
            return True
        import datetime

        value = datetime.datetime.fromisoformat(lease_until)
        return value <= datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _to_job(row) -> Job:
        return Job(
            int(row["id"]),
            row["idempotency_key"],
            row["kind"],
            row["track_id"],
            row["state"],
            int(row["attempts"]),
            int(row["max_attempts"]),
            row["last_error"],
            row["started_at"],
            row["completed_at"],
            row["lease_until"],
        )
