from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from app.operations.log_rotation import rotate_log
class LogRotationTests(unittest.TestCase):
 def test_large_log_is_rotated(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t); log=r/'a.log'; log.write_text('x'*200); out=rotate_log(log_path=log,archive_dir=r/'archive',maximum_size_bytes=100)
   self.assertEqual(out['status'],'rotated'); self.assertEqual(log.read_text(),''); self.assertTrue(Path(out['archive_path']).exists())
if __name__=='__main__':unittest.main()
