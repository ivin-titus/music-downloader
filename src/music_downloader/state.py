from enum import StrEnum


class TrackStatus(StrEnum):
    DISCOVERED = "discovered"
    RESOLVING = "resolving"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    VALIDATING = "validating"
    ARCHIVED = "archived"
    FAILED = "failed"


_ALLOWED: dict[TrackStatus, frozenset[TrackStatus]] = {
    TrackStatus.DISCOVERED: frozenset({TrackStatus.RESOLVING, TrackStatus.FAILED}),
    TrackStatus.RESOLVING: frozenset({TrackStatus.DOWNLOADING, TrackStatus.FAILED}),
    TrackStatus.DOWNLOADING: frozenset({TrackStatus.PROCESSING, TrackStatus.FAILED}),
    TrackStatus.PROCESSING: frozenset({TrackStatus.VALIDATING, TrackStatus.FAILED}),
    TrackStatus.VALIDATING: frozenset({TrackStatus.ARCHIVED, TrackStatus.FAILED}),
    TrackStatus.ARCHIVED: frozenset(),
    TrackStatus.FAILED: frozenset({TrackStatus.RESOLVING, TrackStatus.DOWNLOADING}),
}


def can_transition(current: TrackStatus, target: TrackStatus) -> bool:
    return target in _ALLOWED[current]


def require_transition(current: TrackStatus, target: TrackStatus) -> None:
    if not can_transition(current, target):
        raise ValueError(f"invalid track state transition: {current} -> {target}")
