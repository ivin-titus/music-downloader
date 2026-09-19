from pathlib import Path
import typer
from .config import default_settings
from .db import connect, initialize
from .pipeline import ArchiveService, PlaylistService
from .providers import YtDlpProvider

app=typer.Typer(help="Personal music archive and playlist synchronizer.")

def settings_for(root:Path|None):
    settings=default_settings() if root is None else type(default_settings())(root)
    settings.ensure_directories()
    initialize(settings.database_path)
    return settings

@app.command()
def init(root:Path|None=typer.Option(None,help="Archive root directory."))->None:
    settings=settings_for(root); typer.echo(f"Initialized archive at {settings.root_dir}")

@app.command()
def ingest(url:str,root:Path|None=typer.Option(None,help="Archive root directory."))->None:
    settings=settings_for(root)
    connection=connect(settings.database_path)
    try:
        service=ArchiveService(__import__("music_downloader.repository",fromlist=["ArchiveRepository"]).ArchiveRepository(connection),YtDlpProvider(),settings.music_dir)
        track_id=service.ingest(YtDlpProvider().inspect(url))
        typer.echo(f"Archived track {track_id}")
    finally:
        connection.close()

@app.command()
def playlist(url:str,root:Path|None=typer.Option(None,help="Archive root directory."))->None:
    settings=settings_for(root); connection=connect(settings.database_path)
    try:
        provider=YtDlpProvider()
        archive=ArchiveService(__import__("music_downloader.repository",fromlist=["ArchiveRepository"]).ArchiveRepository(connection),provider,settings.music_dir)
        playlist_id=PlaylistService(archive.repository,archive).sync(provider.playlist(url))
        typer.echo(f"Synchronized playlist {playlist_id}")
    finally:
        connection.close()

@app.command()
def version()->None:
    from . import __version__
    typer.echo(__version__)

if __name__=="__main__": app()
