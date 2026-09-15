from pathlib import Path

from music_downloader.storage import atomic_move, sha256_file


def test_sha256_file(tmp_path: Path) -> None:
    source = tmp_path / "track.part"
    source.write_bytes(b"music")
    assert sha256_file(source) == "80f189984e5ca70287d13342f6daa0db45cba3c131c4e46dc81360f3a4c4f690"


def test_atomic_move(tmp_path: Path) -> None:
    source = tmp_path / "track.part"
    destination = tmp_path / "music" / "track.m4a"
    source.write_bytes(b"music")
    atomic_move(source, destination)
    assert destination.read_bytes() == b"music"
    assert not source.exists()
