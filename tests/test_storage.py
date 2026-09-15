from pathlib import Path

from music_downloader.storage import atomic_move, sha256_file


def test_sha256_file(tmp_path: Path) -> None:
    source = tmp_path / "track.part"
    source.write_bytes(b"music")
    assert sha256_file(source) == "c00dbbc9dadfbe1e232e08e6bf9a0193e9e6f3a8c3b1e5f8b6f5f3a6f2b6d5c5"


def test_atomic_move(tmp_path: Path) -> None:
    source = tmp_path / "track.part"
    destination = tmp_path / "music" / "track.m4a"
    source.write_bytes(b"music")
    atomic_move(source, destination)
    assert destination.read_bytes() == b"music"
    assert not source.exists()
