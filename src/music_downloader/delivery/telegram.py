from __future__ import annotations
import mimetypes, secrets
from pathlib import Path
from urllib.request import Request, urlopen

class TelegramDeliveryError(RuntimeError): pass

class TelegramDelivery:
    def __init__(self,token:str,chat_id:str,api_base:str="https://api.telegram.org")->None:
        if not token or not chat_id: raise ValueError("Telegram token and chat_id are required")
        self.token=token; self.chat_id=chat_id; self.api_base=api_base.rstrip("/")
    def send_file(self,path:Path,caption:str|None=None,timeout:float=60.0)->None:
        if not path.is_file(): raise FileNotFoundError(path)
        boundary=secrets.token_hex(16); body=bytearray()
        def field(name:str,value:str):
            body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
        field("chat_id",self.chat_id)
        if caption: field("caption",caption)
        filename=path.name; mime=mimetypes.guess_type(filename)[0] or "application/octet-stream"; data=path.read_bytes()
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode())
        body.extend(data); body.extend(f"\r\n--{boundary}--\r\n".encode())
        request=Request(f"{self.api_base}/bot{self.token}/sendDocument",data=bytes(body),
                        headers={"Content-Type":f"multipart/form-data; boundary={boundary}"},method="POST")
        with urlopen(request,timeout=timeout) as response:
            if not 200 <= response.status < 300: raise TelegramDeliveryError(f"Telegram HTTP {response.status}")
