"""Explicit backup validation and restore v35.2."""
from __future__ import annotations
import hashlib,json,shutil,sqlite3,tempfile
from pathlib import Path
def _sha(path:Path)->str:
 d=hashlib.sha256()
 with path.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''): d.update(c)
 return d.hexdigest()
def validate_backup(backup_path:Path|str)->dict:
 root=Path(backup_path); manifest_path=root/'manifest.json'; errors=[]; checked=[]
 if not root.exists() or not manifest_path.exists(): return {'status':'invalid','version':'v35.2','valid':False,'errors':['Backup directory or manifest is missing'],'checked_files':[]}
 try: manifest=json.loads(manifest_path.read_text())
 except Exception as e:return {'status':'invalid','version':'v35.2','valid':False,'errors':[f'Manifest could not be read: {e}'],'checked_files':[]}
 for item in manifest.get('files',[]):
  rel=Path(item.get('relative_path','')); path=root/rel
  if not path.exists(): errors.append(f'Missing backup file: {rel}'); continue
  actual=_sha(path)
  if actual!=item.get('sha256'): errors.append(f'Checksum mismatch: {rel}')
  if item.get('category')=='database':
   try:
    c=sqlite3.connect(path); r=c.execute('PRAGMA quick_check').fetchone(); c.close()
    if not r or r[0]!='ok': errors.append(f'SQLite quick_check failed: {rel}')
   except Exception as e: errors.append(f'SQLite validation failed: {rel}: {e}')
  checked.append({'relative_path':str(rel),'sha256':actual,'category':item.get('category')})
 return {'status':'valid' if not errors else 'invalid','version':'v35.2','valid':not errors,'errors':errors,'checked_files':checked,'manifest':manifest}
def restore_backup(*,backup_path:Path|str,destination_root:Path|str,overwrite:bool=False)->dict:
 v=validate_backup(backup_path)
 if not v['valid']: return {'status':'blocked','version':'v35.2','restored_files':[],'validation':v,'errors':['Restore blocked because backup validation failed']}
 src=Path(backup_path); dst_root=Path(destination_root); restored=[]
 try:
  for item in v['manifest'].get('files',[]):
   rel=Path(item['relative_path']); dst=dst_root/rel
   if dst.exists() and not overwrite: raise FileExistsError(f'Destination exists: {dst}')
   dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src/rel,dst); restored.append(str(dst))
  return {'status':'success','version':'v35.2','restored_files':restored,'validation':v}
 except Exception as e:return {'status':'error','version':'v35.2','restored_files':restored,'validation':v,'errors':[str(e)]}
