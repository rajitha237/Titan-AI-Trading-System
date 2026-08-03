"""Non-blocking backup operations snapshot v35.2."""
from __future__ import annotations
from app.operations.backup_scheduler import run_backup_cycle_if_due
def build_backup_operations_snapshot()->dict:
 try:
  cycle=run_backup_cycle_if_due(); return {'status':'success' if cycle.get('status') in {'success','not_due'} else 'error','version':'v35.2','backup_cycle':cycle,'non_blocking':True}
 except Exception as e:return {'status':'error','version':'v35.2','backup_cycle':{'status':'error','errors':[str(e)]},'errors':[str(e)],'non_blocking':True}
