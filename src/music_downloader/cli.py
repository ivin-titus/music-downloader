from pathlib import Path

import typer

from .config import default_settings
from .db import initialize

app = typer.Typer(help="Personal music archive and playlist synchronizer.")


@app.command()
def init(root: Path | None = typer.Option(None, help="Archive root directory.")) -> None:
    settings = default_settings() if root is None else type(default_settings())(root)
    settings.ensure_directories()
    initialize(settings.database_path)
    typer.echo(f"Initialized archive at {settings.root_dir}")


@app.command()
def version() -> None:
    from . import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
