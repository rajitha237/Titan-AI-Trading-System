from __future__ import annotations
import json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from app.operations.backup_scheduler import run_backup_cycle_if_due
class BackupSchedulerTests(unittest.TestCase):
 def test_recent_backup_is_not_due(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t); s=r/'state.json'; s.write_text(json.dumps({'last_backup_at':datetime.now(timezone.utc).isoformat()})); out=run_backup_cycle_if_due(backup_dir=r/'b',state_file=s); self.assertEqual(out['status'],'not_due')
 def test_due_backup_runs_manager(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t)
   with patch('app.operations.backup_scheduler.create_backup',return_value={'status':'success','backup_path':str(r/'b/x')}),patch('app.operations.backup_scheduler.apply_retention_policy',return_value={'status':'success','removed':[],'retained':[]}): out=run_backup_cycle_if_due(backup_dir=r/'b',state_file=r/'s.json')
   self.assertEqual(out['status'],'success'); self.assertTrue(out['due'])
if __name__=='__main__':unittest.main()
