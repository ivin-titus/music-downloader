import pytest

from music_downloader.state import TrackStatus, can_transition, require_transition


def test_happy_path_is_explicit() -> None:
    assert can_transition(TrackStatus.DISCOVERED, TrackStatus.RESOLVING)
    assert can_transition(TrackStatus.VALIDATING, TrackStatus.ARCHIVED)


def test_invalid_transition_is_rejected() -> None:
    with pytest.raises(ValueError):
        require_transition(TrackStatus.DISCOVERED, TrackStatus.ARCHIVED)
