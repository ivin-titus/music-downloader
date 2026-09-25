from __future__ import annotations

import json
from pathlib import Path

import typer

from .config import default_settings
from .db import connect, initialize
from .jobs import JobRepository, JobState
from .models import SourceTrack
from .pipeline import ArchiveService, DownloadOrchestrator, PlaylistService
from .providers import YtDlpProvider
from .repository import ArchiveRepository

app = typer.Typer(help="Personal music archive and playlist synchronizer.")


def settings_for(root: Path | None):
    settings = default_settings() if root is None else type(default_settings())(root)
    settings.ensure_directories()
    initialize(settings.database_path)
    return settings


def repository_for(settings) -> ArchiveRepository:
    return ArchiveRepository(connect(settings.database_path))


@app.command()
def init(root: Path | None = typer.Option(None, help="Archive root directory.")) -> None:
    settings = settings_for(root)
    typer.echo(f"Initialized archive at {settings.root_dir}")


@app.command()
def ingest(url: str, root: Path | None = typer.Option(None, help="Archive root directory.")) -> None:
    settings = settings_for(root)
    repository = repository_for(settings)
    try:
        provider = YtDlpProvider()
        archive = ArchiveService(repository, provider, settings.music_dir)
        track_id = DownloadOrchestrator(JobRepository(repository), archive).ingest(
            provider.inspect(url)
        )
        typer.echo(f"Archived track {track_id}")
    finally:
        repository.close()


@app.command()
def playlist(
    url: str,
    root: Path | None = typer.Option(None, help="Archive root directory and database."),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Directory where this playlist's MP3 files are stored.",
    ),
) -> None:
    """Download and archive every supported item in a playlist."""
    settings = settings_for(root)
    repository = repository_for(settings)
    music_root = (output or settings.music_dir).expanduser().resolve()
    music_root.mkdir(parents=True, exist_ok=True)
    try:
        provider = YtDlpProvider()
        archive = ArchiveService(repository, provider, music_root)
        jobs = JobRepository(repository)
        playlist_id = PlaylistService(
            repository,
            archive,
            DownloadOrchestrator(jobs, archive),
        ).sync(provider.playlist(url))
        if playlist_id is None:
            raise typer.BadParameter("playlist contained no supported items")
        typer.echo(f"Synchronized playlist {playlist_id} into {music_root}")
    finally:
        repository.close()


@app.command()
def status(root: Path | None = typer.Option(None, help="Archive root directory.")) -> None:
    """Show track and job state counts."""
    settings = settings_for(root)
    repository = repository_for(settings)
    try:
        track_rows = repository.connection.execute(
            "SELECT status, COUNT(*) AS count FROM tracks GROUP BY status ORDER BY status"
        ).fetchall()
        job_rows = repository.connection.execute(
            "SELECT state, COUNT(*) AS count FROM jobs GROUP BY state ORDER BY state"
        ).fetchall()
        if not track_rows:
            typer.echo("No tracks in archive.")
        else:
            typer.echo("Tracks:")
            for row in track_rows:
                typer.echo(f"  {row['status']}: {row['count']}")
        typer.echo("Jobs:")
        if not job_rows:
            typer.echo("  none")
        else:
            for row in job_rows:
                typer.echo(f"  {row['state']}: {row['count']}")
    finally:
        repository.close()


@app.command()
def retry(root: Path | None = typer.Option(None, help="Archive root directory.")) -> None:
    """Recover stale jobs and retry pending ingest jobs."""
    settings = settings_for(root)
    repository = repository_for(settings)
    jobs = JobRepository(repository)
    provider = YtDlpProvider()
    archive = ArchiveService(repository, provider, settings.music_dir)
    orchestrator = DownloadOrchestrator(jobs, archive)
    try:
        recovered = jobs.recover_stale()
        rows = repository.connection.execute(
            """SELECT id,idempotency_key FROM jobs
               WHERE state=? AND kind='ingest' ORDER BY id""",
            (JobState.PENDING,),
        ).fetchall()
        succeeded = 0
        failed = 0
        for row in rows:
            provider_name, source_id = str(row["idempotency_key"]).split(":", 1)
            source_row = repository.connection.execute(
                """SELECT metadata_json FROM sources
                   WHERE provider=? AND source_id=?""",
                (provider_name, source_id),
            ).fetchone()
            if source_row is None:
                typer.echo(
                    f"Job {row['id']}: source metadata is unavailable for retry.",
                    err=True,
                )
                failed += 1
                continue
            source = SourceTrack(**json.loads(source_row["metadata_json"]))
            try:
                orchestrator.ingest(source)
            except Exception:
                failed += 1
            else:
                succeeded += 1
        typer.echo(f"Recovered {recovered} stale job(s); retried {succeeded} job(s).")
        if failed:
            typer.echo(f"{failed} job(s) could not be retried.", err=True)
            raise typer.Exit(code=1)
    finally:
        repository.close()


@app.command()
def verify(root: Path | None = typer.Option(None, help="Archive root directory.")) -> None:
    """Verify archived file presence and stored SHA-256 integrity."""
    settings = settings_for(root)
    repository = repository_for(settings)
    try:
        problems = repository.verify_archive()
        if problems:
            for problem in problems:
                typer.echo(f"ERROR: {problem}", err=True)
            raise typer.Exit(code=1)
        typer.echo("Archive verification passed.")
    finally:
        repository.close()


@app.command()
def version() -> None:
    from . import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
