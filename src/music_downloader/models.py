from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SourceTrack:
    provider: str
    source_id: str
    title: str
    url: str | None = None
    artist: str | None = None
    album: str | None = None
    duration_ms: int | None = None
    artwork_url: str | None = None

@dataclass(frozen=True, slots=True)
class ResolvedTrack:
    title: str
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    duration_ms: int | None = None
    recording_key: str | None = None
    confidence: float = 0.0
