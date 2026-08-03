from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from app.operations.deployment_checklist import build_deployment_checklist


class DeploymentChecklistTests(unittest.TestCase):
    def test_required_paths_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app/trader").mkdir(parents=True)
            (root / "app/trader/auto_testnet_runner.py").write_text("")
            (root / "requirements.txt").write_text("")
            (root / ".env.example").write_text("")
            (root / "tests").mkdir()
            result = build_deployment_checklist(project_root=root)
        self.assertTrue(result["ready"])


if __name__ == "__main__":
    unittest.main()
