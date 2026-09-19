from __future__ import annotations
import json, subprocess
from pathlib import Path
from urllib.parse import urlparse
from music_downloader.models import SourceTrack
from .base import Provider, ProviderItem

class YtDlpProvider(Provider):
    name="yt-dlp"
    def __init__(self, executable:str="yt-dlp")->None: self.executable=executable
    def inspect(self,url:str)->SourceTrack:
        info=self._run(["--dump-single-json","--no-playlist",url])
        sid=str(info.get("id") or "")
        if not sid: raise ValueError("yt-dlp did not return a source id")
        duration=info.get("duration")
        return SourceTrack(self.name,sid,str(info.get("title") or Path(urlparse(url).path).stem),url,info.get("artist") or info.get("uploader"),info.get("album"),int(float(duration)*1000) if duration is not None else None)
    def playlist(self,url:str):
        info=self._run(["--flat-playlist","--dump-single-json",url])
        for position,entry in enumerate(info.get("entries") or []):
            if not entry.get("id"): continue
            duration=entry.get("duration")
            source=SourceTrack(self.name,str(entry["id"]),str(entry.get("title") or entry["id"]),entry.get("url") or entry.get("webpage_url"),entry.get("artist") or entry.get("uploader"),None,int(float(duration)*1000) if duration is not None else None)
            yield ProviderItem(source,str(info.get("id") or url),str(info.get("title") or "Playlist"),url,position)
    def download(self,source:SourceTrack,destination:str)->None:
        target=Path(destination); target.parent.mkdir(parents=True,exist_ok=True)
        self._run(["--no-playlist","--format","bestaudio/best","--extract-audio","--audio-format","mp3","--output",str(target),source.url or source.source_id])
    def _run(self,args:list[str])->dict:
        completed=subprocess.run([self.executable,*args],check=True,capture_output=True,text=True)
        return json.loads(completed.stdout) if "--dump-single-json" in args else {}
