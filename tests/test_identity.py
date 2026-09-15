from music_downloader.identity import normalize_text, resolve_source_track
from music_downloader.models import SourceTrack


def test_normalize_text_is_stable_for_common_separators() -> None:
    assert normalize_text("  Daft.Night_-Mix  ") == "daft night mix"


def test_source_title_is_preserved_by_base_resolver() -> None:
    source = SourceTrack(
        provider="example",
        source_id="123",
        title="Banger 🔥 (Official Audio)",
        artist="Artist",
    )
    resolved = resolve_source_track(source)
    assert resolved.title == source.title
    assert resolved.artist == source.artist
