import re
import unicodedata
from music_downloader.models import ResolvedTrack, SourceTrack

_SEPARATORS = re.compile(r"[\s._-]+")
_VARIANTS = re.compile(r"\b(live|acoustic|remix|remaster(?:ed)?|demo|instrumental|radio edit|mono|stereo|version|karaoke)\b", re.I)

def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    return _SEPARATORS.sub(" ", value)

def normalized_identity(track: SourceTrack) -> tuple[str, str, int | None]:
    return normalize_text(track.artist), normalize_text(track.title), track.duration_ms

def has_meaningful_variant(title: str | None) -> bool:
    return bool(_VARIANTS.search(title or ""))

def identity_score(source: SourceTrack, candidate: ResolvedTrack) -> float:
    score = 0.0
    if normalize_text(source.title) == normalize_text(candidate.title):
        score += 0.55
    if source.artist and candidate.artist and normalize_text(source.artist) == normalize_text(candidate.artist):
        score += 0.30
    if source.album and candidate.album and normalize_text(source.album) == normalize_text(candidate.album):
        score += 0.10
    if source.duration_ms and candidate.duration_ms:
        delta = abs(source.duration_ms - candidate.duration_ms)
        if delta <= 2000:
            score += 0.10
        elif delta <= 5000:
            score += 0.05
    if has_meaningful_variant(source.title) != has_meaningful_variant(candidate.title):
        score -= 0.35
    return max(0.0, min(1.0, score))

def resolve_source_track(track: SourceTrack) -> ResolvedTrack:
    return ResolvedTrack(
        title=track.title.strip(),
        artist=track.artist.strip() if track.artist else None,
        album=track.album.strip() if track.album else None,
        duration_ms=track.duration_ms,
        confidence=0.25,
    )
