import re
import unicodedata

from .models import ResolvedTrack, SourceTrack

_SEPARATORS = re.compile(r"[\s._-]+")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    value = _SEPARATORS.sub(" ", value)
    return value


def normalized_identity(track: SourceTrack) -> tuple[str, str, int | None]:
    return (
        normalize_text(track.artist),
        normalize_text(track.title),
        track.duration_ms,
    )


def resolve_source_track(track: SourceTrack) -> ResolvedTrack:
    """Minimal deterministic resolver; provider corroboration comes later."""
    return ResolvedTrack(
        title=track.title.strip(),
        artist=track.artist.strip() if track.artist else None,
        album=track.album.strip() if track.album else None,
        duration_ms=track.duration_ms,
        confidence=0.25,
    )
