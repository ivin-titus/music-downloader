from __future__ import annotations
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from music_downloader.models import SourceTrack

@dataclass(frozen=True, slots=True)
class ProviderItem:
    source:SourceTrack
    playlist_source_id:str|None=None
    playlist_title:str|None=None
    playlist_url:str|None=None
    position:int|None=None

class Provider(Protocol):
    name:str
    def inspect(self,url:str)->SourceTrack: ...
    def playlist(self,url:str)->Iterable[ProviderItem]: ...
    def download(self,source:SourceTrack,destination:str)->None: ...
