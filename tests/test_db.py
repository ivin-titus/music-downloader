from pathlib import Path

from music_downloader.db import connect, initialize
from music_downloader.migrations import applied_versions


def test_initialize_creates_core_tables_and_records_migration(tmp_path: Path) -> None:
    database = tmp_path / "archive.db"
    initialize(database)

    with connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        versions = applied_versions(connection)

    assert {"tracks", "sources", "playlists", "playlist_tracks", "schema_migrations"} <= tables
    assert versions == {1}


def test_initialize_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "archive.db"
    initialize(database)
    initialize(database)

    with connect(database) as connection:
        assert applied_versions(connection) == {1}
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
