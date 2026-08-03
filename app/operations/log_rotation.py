"""Gzip log rotation v35.2."""
from __future__ import annotations
import gzip,shutil
from datetime import datetime,timezone
from pathlib import Path
def rotate_log(*,log_path:Path|str,archive_dir:Path|str,maximum_size_bytes:int=10*1024*1024)->dict:
 log=Path(log_path); archive=Path(archive_dir)
 if not log.exists(): return {'status':'skipped','version':'v35.2','reason':'Log file does not exist','archive_path':None}
 size=log.stat().st_size
 if size<max(1,int(maximum_size_bytes)): return {'status':'skipped','version':'v35.2','reason':'Log file is below rotation threshold','archive_path':None,'size_bytes':size}
 archive.mkdir(parents=True,exist_ok=True); out=archive/f"{log.name}.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.gz"
 with log.open('rb') as s, gzip.open(out,'wb') as d: shutil.copyfileobj(s,d)
 log.write_text('',encoding='utf-8')
 return {'status':'rotated','version':'v35.2','archive_path':str(out),'original_size_bytes':size,'compressed_size_bytes':out.stat().st_size}
