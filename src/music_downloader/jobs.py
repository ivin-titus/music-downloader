from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from music_downloader.repository import ArchiveRepository

class JobState(StrEnum):
    PENDING="pending"; RUNNING="running"; SUCCEEDED="succeeded"; FAILED="failed"

@dataclass(frozen=True, slots=True)
class Job:
    id:int; idempotency_key:str; kind:str; track_id:int|None; state:JobState
    attempts:int; max_attempts:int; last_error:str|None

class JobRepository:
    def __init__(self, archive:ArchiveRepository): self.archive=archive
    def enqueue(self, *, idempotency_key:str, kind:str, track_id:int|None=None, max_attempts:int=3)->int:
        if max_attempts<1: raise ValueError("max_attempts must be positive")
        with self.archive.transaction():
            row=self.archive.connection.execute("SELECT id FROM jobs WHERE idempotency_key=?",(idempotency_key,)).fetchone()
            if row: return int(row["id"])
            return int(self.archive.connection.execute(
                "INSERT INTO jobs(idempotency_key,kind,track_id,max_attempts) VALUES(?,?,?,?) RETURNING id",
                (idempotency_key,kind,track_id,max_attempts)).fetchone()["id"])
    def claim(self, job_id:int)->Job:
        with self.archive.transaction():
            row=self.archive.connection.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
            if row is None: raise KeyError(f"unknown job id: {job_id}")
            if row["state"]==JobState.SUCCEEDED.value: return self._to_job(row)
            if row["state"]==JobState.RUNNING.value: raise RuntimeError(f"job {job_id} is already running")
            if row["attempts"]>=row["max_attempts"]: raise RuntimeError(f"job {job_id} exhausted its retry budget")
            self.archive.connection.execute("UPDATE jobs SET state=?,attempts=attempts+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",(JobState.RUNNING.value,job_id))
            return self._to_job(self.archive.connection.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone())
    def succeed(self, job_id:int)->None:
        with self.archive.transaction():
            cur=self.archive.connection.execute("UPDATE jobs SET state=?,last_error=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND state=?",(JobState.SUCCEEDED.value,job_id,JobState.RUNNING.value))
            if cur.rowcount!=1: raise RuntimeError(f"job {job_id} is not running")
    def fail(self, job_id:int, error:str)->JobState:
        if not error.strip(): raise ValueError("error must not be empty")
        with self.archive.transaction():
            row=self.archive.connection.execute("SELECT attempts,max_attempts,state FROM jobs WHERE id=?",(job_id,)).fetchone()
            if row is None: raise KeyError(f"unknown job id: {job_id}")
            if row["state"]!=JobState.RUNNING.value: raise RuntimeError(f"job {job_id} is not running")
            state=JobState.PENDING if row["attempts"]<row["max_attempts"] else JobState.FAILED
            self.archive.connection.execute("UPDATE jobs SET state=?,last_error=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(state.value,error[:4000],job_id))
            return state
    def get(self, job_id:int)->Job:
        row=self.archive.connection.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
        if row is None: raise KeyError(f"unknown job id: {job_id}")
        return self._to_job(row)
    @staticmethod
    def _to_job(row)->Job:
        return Job(int(row["id"]),row["idempotency_key"],row["kind"],row["track_id"],JobState(row["state"]),int(row["attempts"]),int(row["max_attempts"]),row["last_error"])
