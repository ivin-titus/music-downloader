from pathlib import Path

from music_downloader.db import connect, initialize


def test_initialize_creates_core_tables(tmp_path: Path) -> None:
    database = tmp_path / "archive.db"
    initialize(database)

    with connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {"tracks", "sources", "playlists", "playlist_tracks"} <= tables
