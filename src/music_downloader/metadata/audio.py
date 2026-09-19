from __future__ import annotations
from pathlib import Path
from mutagen import File
from mutagen.id3 import ID3, APIC, TIT2, TALB, TPE1, TPE2
from music_downloader.models import ResolvedTrack

class MetadataError(ValueError): pass

def validate_audio(path:Path)->None:
    if not path.is_file() or path.stat().st_size<1024: raise MetadataError("audio file is missing or unexpectedly small")
    audio=File(path)
    if audio is None or getattr(audio,"info",None) is None: raise MetadataError("file is not recognized as audio")

def tag_mp3(path:Path,track:ResolvedTrack,artwork:bytes|None=None,mime_type:str="image/jpeg")->None:
    validate_audio(path)
    tags=ID3(path)
    for key in ("TIT2","TPE1","TALB","TPE2","APIC"): tags.delall(key)
    tags.add(TIT2(encoding=3,text=track.title))
    if track.artist: tags.add(TPE1(encoding=3,text=track.artist))
    if track.album: tags.add(TALB(encoding=3,text=track.album))
    if track.album_artist: tags.add(TPE2(encoding=3,text=track.album_artist))
    if artwork: tags.add(APIC(encoding=3,mime=mime_type,type=3,data=artwork,desc="Cover"))
    tags.save(path)
