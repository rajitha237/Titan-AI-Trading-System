"""Due-check backup scheduler v35.2."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
from app.operations.backup_manager import BACKUP_DIR,create_backup
from app.operations.retention_policy import apply_retention_policy
def run_backup_cycle_if_due(*,interval_hours:float=24.0,backup_dir:Path|None=None,state_file:Path|None=None)->dict:
 root=Path(backup_dir or BACKUP_DIR); state=Path(state_file or root/'backup_scheduler_state.json'); data={}
 if state.exists():
  try:data=json.loads(state.read_text())
  except Exception:data={}
 last=data.get('last_backup_at'); parsed=None
 if last:
  try:parsed=datetime.fromisoformat(last)
  except ValueError:parsed=None
 now=datetime.now(timezone.utc); due=parsed is None or (now-parsed).total_seconds()>=max(1.0,float(interval_hours)*3600)
 if not due:return {'status':'not_due','version':'v35.2','due':False,'last_backup_at':last,'non_blocking':True}
 backup=create_backup(backup_dir=root,label='scheduled'); retention=apply_retention_policy(directory=root,maximum_age_days=30,maximum_items=30)
 if backup.get('status')=='success': state.parent.mkdir(parents=True,exist_ok=True); state.write_text(json.dumps({'last_backup_at':now.isoformat(timespec='milliseconds'),'last_backup_path':backup.get('backup_path')},indent=2))
 return {'status':'success' if backup.get('status')=='success' else 'error','version':'v35.2','due':True,'backup':backup,'retention':retention,'non_blocking':True}
