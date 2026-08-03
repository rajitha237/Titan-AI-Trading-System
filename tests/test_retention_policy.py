from __future__ import annotations
import os,tempfile,time,unittest
from pathlib import Path
from app.operations.retention_policy import apply_retention_policy
class RetentionPolicyTests(unittest.TestCase):
 def test_maximum_item_count_is_enforced(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t)
   for i in range(4):
    p=r/f'i{i}'; p.write_text(str(i)); ts=time.time()-i; os.utime(p,(ts,ts))
   out=apply_retention_policy(directory=r,maximum_age_days=365,maximum_items=2); self.assertEqual(len(out['retained']),2); self.assertEqual(len(out['removed']),2)
if __name__=='__main__':unittest.main()
