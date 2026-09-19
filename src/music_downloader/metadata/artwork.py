from __future__ import annotations
import hashlib
from dataclasses import dataclass
from urllib.request import Request, urlopen

class ArtworkError(ValueError): pass

@dataclass(frozen=True, slots=True)
class Artwork:
    data: bytes
    mime_type: str
    sha256: str

def validate_artwork(data: bytes, max_bytes: int = 5 * 1024 * 1024) -> Artwork:
    if not data or len(data)>max_bytes: raise ArtworkError("artwork is empty or exceeds the size limit")
    signatures=((b"\xff\xd8\xff","image/jpeg"),(b"\x89PNG\r\n\x1a\n","image/png"),(b"RIFF","image/webp"))
    mime=None
    for signature,candidate in signatures:
        if data.startswith(signature): mime=candidate; break
    if mime=="image/webp" and data[8:12]!=b"WEBP": raise ArtworkError("invalid webp container")
    if mime is None: raise ArtworkError("artwork is not a supported image")
    return Artwork(data,mime,hashlib.sha256(data).hexdigest())

def fetch_artwork(url: str, timeout: float = 15.0, max_bytes: int = 5 * 1024 * 1024) -> Artwork:
    request=Request(url,headers={"User-Agent":"music-downloader/0.1"})
    with urlopen(request,timeout=timeout) as response:
        length=response.headers.get("Content-Length")
        if length and int(length)>max_bytes: raise ArtworkError("remote artwork exceeds size limit")
        data=response.read(max_bytes+1)
    return validate_artwork(data,max_bytes)
