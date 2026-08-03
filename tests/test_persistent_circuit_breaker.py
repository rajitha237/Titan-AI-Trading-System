from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.service import service_state_store
from app.monitoring.persistent_circuit_breaker import (
    PersistentCircuitBreaker,
)


class PersistentCircuitBreakerTests(
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

    def test_open_state_survives_new_instance(self):
        first = PersistentCircuitBreaker(
            state_key="breaker",
            failure_threshold=1,
            recovery_timeout_seconds=60,
        )
        first.record_failure(
            "network"
        )

        second = PersistentCircuitBreaker(
            state_key="breaker",
            failure_threshold=1,
            recovery_timeout_seconds=60,
        )

        self.assertEqual(
            second.snapshot()["state"],
            "OPEN",
        )

    def test_success_persists_closed_state(self):
        breaker = PersistentCircuitBreaker(
            state_key="breaker",
            failure_threshold=1,
            recovery_timeout_seconds=60,
        )
        breaker.record_failure(
            "network"
        )
        breaker.record_success()

        restored = (
            PersistentCircuitBreaker(
                state_key="breaker",
                failure_threshold=1,
                recovery_timeout_seconds=60,
            )
        )

        self.assertEqual(
            restored.snapshot()["state"],
            "CLOSED",
        )


if __name__ == "__main__":
    unittest.main()
