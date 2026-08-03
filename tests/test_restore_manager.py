from __future__ import annotations
import sqlite3,tempfile,unittest
from pathlib import Path
from app.operations.backup_manager import create_backup
from app.operations.restore_manager import validate_backup,restore_backup
class RestoreManagerTests(unittest.TestCase):
 def test_valid_backup_can_be_restored(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t); db=r/'source.db'; c=sqlite3.connect(db); c.execute('CREATE TABLE x(v TEXT)'); c.commit(); c.close(); b=create_backup(backup_dir=r/'backups',database_paths=[db],config_paths=[])
   self.assertTrue(validate_backup(b['backup_path'])['valid']); out=restore_backup(backup_path=b['backup_path'],destination_root=r/'restore')
   self.assertEqual(out['status'],'success'); self.assertTrue((r/'restore/databases/source.db').exists())
if __name__=='__main__':unittest.main()
