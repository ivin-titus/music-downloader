import pytest
from music_downloader.metadata.artwork import ArtworkError, validate_artwork

def test_rejects_html_disguised_as_artwork():
    with pytest.raises(ArtworkError):
        validate_artwork(b"<html><body>error</body></html>")

def test_accepts_png_signature():
    artwork=validate_artwork(b"\x89PNG\r\n\x1a\n"+b"0"*32)
    assert artwork.mime_type=="image/png"
    assert len(artwork.sha256)==64
