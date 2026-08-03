from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.service import service_state_store
from app.service.service_state_manager import (
    begin_service_cycle,
    build_service_state_snapshot,
    complete_service_cycle,
)


class ServiceStateManagerTests(
    unittest.TestCase
):
    def setUp(self):
        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )
        self.patch = patch.object(
            service_state_store,
            "DB_PATH",
            Path(self.temp_dir.name)
            / "service.db",
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp_dir.cleanup()

    def test_cycle_writes_start_and_completion(self):
        context = begin_service_cycle(
            mode="ANALYSIS_ONLY"
        )

        completed = (
            complete_service_cycle(
                cycle_context=context,
                result={
                    "status": "skipped",
                    "mode": "ANALYSIS_ONLY",
                    "execution": {
                        "submitted": False,
                    },
                },
            )
        )

        self.assertEqual(
            completed["status"],
            "skipped",
        )
        self.assertTrue(
            build_service_state_snapshot()[
                "persistent"
            ]
        )


if __name__ == "__main__":
    unittest.main()
