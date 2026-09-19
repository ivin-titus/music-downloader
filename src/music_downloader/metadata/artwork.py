from __future__ import annotations
import imghdr
from dataclasses import dataclass
class ArtworkError(ValueError): pass
@dataclass(frozen=True,slots=True)
class Artwork:
    data:bytes; mime_type:str
def validate_artwork(data:bytes,max_bytes:int=5*1024*1024)->Artwork:
    if not data or len(data)>max_bytes: raise ArtworkError("artwork is empty or exceeds the size limit")
    kind=imghdr.what(None,h=data)
    mime={"jpeg":"image/jpeg","png":"image/png","webp":"image/webp"}.get(kind)
    if mime is None: raise ArtworkError("artwork is not a supported image")
    return Artwork(data,mime)
