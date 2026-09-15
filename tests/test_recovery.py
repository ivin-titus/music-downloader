from pathlib import Path

from music_downloader.recovery import remove_stale_partials


def test_remove_stale_partials(tmp_path: Path) -> None:
    stale = tmp_path / "nested" / "track.part"
    stale.parent.mkdir()
    stale.write_bytes(b"partial")
    keep = tmp_path / "track.m4a"
    keep.write_bytes(b"complete")

    removed = remove_stale_partials(tmp_path)

    assert removed == [stale]
    assert not stale.exists()
    assert keep.exists()
