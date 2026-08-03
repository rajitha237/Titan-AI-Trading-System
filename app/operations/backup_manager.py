"""Atomic, checksummed TitanAI backups v35.2."""
from __future__ import annotations
import hashlib,json,os,shutil,sqlite3,tempfile
from datetime import datetime,timezone
from pathlib import Path
APP_ROOT=Path(__file__).resolve().parents[1]
DATA_DIR=APP_ROOT/'data'; BACKUP_DIR=APP_ROOT/'backups'
DEFAULT_DATABASES=(DATA_DIR/'titanai_service_state.db',DATA_DIR/'titanai_order_recovery.db',DATA_DIR/'titanai_notifications.db',DATA_DIR/'titanai_performance.db')
DEFAULT_CONFIG_FILES=(APP_ROOT.parent/'.env.example',APP_ROOT.parent/'requirements.txt')
def _sha(path:Path)->str:
 d=hashlib.sha256()
 with path.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''): d.update(c)
 return d.hexdigest()
def _copy_db(src:Path,dst:Path)->None:
 dst.parent.mkdir(parents=True,exist_ok=True); a=sqlite3.connect(src); b=sqlite3.connect(dst)
 try:a.backup(b)
 finally:b.close(); a.close()
def create_backup(*,backup_dir:Path|None=None,database_paths=None,config_paths=None,label:str='manual')->dict:
 root=Path(backup_dir or BACKUP_DIR); root.mkdir(parents=True,exist_ok=True)
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); safe=''.join(c if c.isalnum() or c in '-_' else '_' for c in str(label)).strip('_') or 'backup'
 final=root/f'{stamp}_{safe}'; temp=Path(tempfile.mkdtemp(prefix='.titanai_backup_',dir=root)); items=[]; warnings=[]
 try:
  for src in (database_paths if database_paths is not None else DEFAULT_DATABASES):
   src=Path(src)
   if not src.exists(): warnings.append(f'Database missing: {src}'); continue
   dst=temp/'databases'/src.name; _copy_db(src,dst); items.append({'category':'database','source':str(src),'relative_path':str(dst.relative_to(temp)),'size_bytes':dst.stat().st_size,'sha256':_sha(dst)})
  for src in (config_paths if config_paths is not None else DEFAULT_CONFIG_FILES):
   src=Path(src)
   if not src.exists(): warnings.append(f'Config file missing: {src}'); continue
   dst=temp/'config'/src.name; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); items.append({'category':'config','source':str(src),'relative_path':str(dst.relative_to(temp)),'size_bytes':dst.stat().st_size,'sha256':_sha(dst)})
  manifest={'status':'complete','version':'v35.2','created_at':datetime.now(timezone.utc).isoformat(timespec='milliseconds'),'label':safe,'file_count':len(items),'files':items,'warnings':warnings}
  (temp/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
  if final.exists(): shutil.rmtree(final)
  os.replace(temp,final)
  return {'status':'success','version':'v35.2','backup_path':str(final),'manifest':manifest,'warnings':warnings,'non_blocking':True}
 except Exception as e:
  shutil.rmtree(temp,ignore_errors=True); return {'status':'error','version':'v35.2','backup_path':None,'manifest':None,'warnings':warnings,'errors':[str(e)],'non_blocking':True}
