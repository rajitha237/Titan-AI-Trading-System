from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.performance import performance_history
from app.performance.performance_history import (
    list_performance_snapshots,
    save_performance_snapshot,
)


class PerformanceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch = patch.object(
            performance_history,
            "DB_PATH",
            Path(self.temp_dir.name) / "performance.db",
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp_dir.cleanup()

    def test_snapshot_is_idempotent(self):
        for value in (1, 2):
            save_performance_snapshot(
                snapshot_key="daily:2026-08-02",
                payload={"value": value},
            )
        rows = list_performance_snapshots()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["payload"]["value"], 2)


if __name__ == "__main__":
    unittest.main()
