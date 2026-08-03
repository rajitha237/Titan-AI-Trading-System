from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.service import service_state_store
from app.service.service_state_store import (
    get_latest_heartbeat,
    get_state,
    record_heartbeat,
    set_state,
)


class ServiceStateStoreTests(
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

    def test_state_round_trip(self):
        set_state(
            "example",
            {
                "status": "ok",
            },
        )

        self.assertEqual(
            get_state("example")[
                "status"
            ],
            "ok",
        )

    def test_heartbeat_round_trip(self):
        record_heartbeat(
            service_name="test",
            status="RUNNING",
            mode="ANALYSIS_ONLY",
            cycle_id="abc",
            payload={
                "value": 1,
            },
        )

        latest = get_latest_heartbeat(
            "test"
        )

        self.assertEqual(
            latest["cycle_id"],
            "abc",
        )


if __name__ == "__main__":
    unittest.main()
