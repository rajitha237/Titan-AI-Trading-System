"""Age and count retention v35.2."""
from __future__ import annotations
import shutil
from datetime import datetime,timezone
from pathlib import Path
def apply_retention_policy(*,directory:Path|str,maximum_age_days:int=30,maximum_items:int=30)->dict:
 root=Path(directory)
 if not root.exists(): return {'status':'success','version':'v35.2','removed':[],'retained':[]}
 now=datetime.now(timezone.utc).timestamp(); max_age=max(0,int(maximum_age_days))*86400
 items=sorted([p for p in root.iterdir() if not p.name.startswith('.')],key=lambda p:p.stat().st_mtime,reverse=True); removed=[]; retained=[]
 for i,p in enumerate(items):
  old=max_age>0 and now-p.stat().st_mtime>max_age; excess=i>=max(1,int(maximum_items))
  if old or excess:
   shutil.rmtree(p) if p.is_dir() else p.unlink(); removed.append(str(p))
  else: retained.append(str(p))
 return {'status':'success','version':'v35.2','removed':removed,'retained':retained}
