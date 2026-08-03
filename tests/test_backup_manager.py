from __future__ import annotations
import sqlite3,tempfile,unittest
from pathlib import Path
from app.operations.backup_manager import create_backup
class BackupManagerTests(unittest.TestCase):
 def test_creates_manifest_and_database_copy(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t); db=r/'source.db'; c=sqlite3.connect(db); c.execute('CREATE TABLE x(v TEXT)'); c.commit(); c.close()
   out=create_backup(backup_dir=r/'backups',database_paths=[db],config_paths=[],label='unit')
   self.assertEqual(out['status'],'success'); self.assertTrue((Path(out['backup_path'])/'manifest.json').exists()); self.assertEqual(out['manifest']['file_count'],1)
if __name__=='__main__':unittest.main()
