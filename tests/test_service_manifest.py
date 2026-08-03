from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from app.operations.service_manifest import build_service_manifest, write_service_manifest


class ServiceManifestTests(unittest.TestCase):
    def test_manifest_is_testnet_only(self):
        with tempfile.TemporaryDirectory() as temp:
            result = build_service_manifest(project_root=temp, interval_seconds=30)
        self.assertTrue(result["testnet_only"])
        self.assertEqual(result["interval_seconds"], 60)

    def test_manifest_can_be_written(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "manifest.json"
            result = write_service_manifest(project_root=temp, destination=destination)
            self.assertTrue(destination.exists())
            self.assertEqual(result["status"], "success")


if __name__ == "__main__":
    unittest.main()
