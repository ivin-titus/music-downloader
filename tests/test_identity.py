from music_downloader.identity import identity_score, has_meaningful_variant
from music_downloader.models import ResolvedTrack, SourceTrack

def test_semantic_match_uses_metadata_and_duration():
    source=SourceTrack("a","1","Song","https://x","Artist",duration_ms=180000)
    candidate=ResolvedTrack("song","artist",duration_ms=181000)
    assert identity_score(source,candidate)>=0.75

def test_meaningful_variants_are_not_collapsed():
    source=SourceTrack("a","1","Song (Live)","https://x","Artist")
    candidate=ResolvedTrack("Song","Artist")
    assert has_meaningful_variant(source.title)
    assert identity_score(source,candidate)<0.75
