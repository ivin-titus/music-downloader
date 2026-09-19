from __future__ import annotations
import subprocess
from pathlib import Path

class RsyncError(RuntimeError): pass

class RsyncDelivery:
    def __init__(self,host:str,remote_path:str,ssh_options:tuple[str,...]=())->None:
        if not host or not remote_path: raise ValueError("host and remote_path are required")
        self.host=host; self.remote_path=remote_path; self.ssh_options=ssh_options
    def sync(self,source_root:Path,dry_run:bool=False)->None:
        if not source_root.is_dir(): raise FileNotFoundError(source_root)
        command=["rsync","-a","--partial","--ignore-existing"]
        if dry_run: command.append("--dry-run")
        if self.ssh_options: command.extend(["-e","ssh "+" ".join(self.ssh_options)])
        command.extend([str(source_root)+"/",f"{self.host}:{self.remote_path.rstrip('/')}/"])
        completed=subprocess.run(command,capture_output=True,text=True)
        if completed.returncode!=0: raise RsyncError(completed.stderr.strip() or "rsync failed")
