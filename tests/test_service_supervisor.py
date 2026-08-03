from __future__ import annotations

import unittest

from app.operations.service_supervisor import (
    ServiceSupervisor,
)


class ServiceSupervisorTests(
    unittest.TestCase
):
    def test_healthy_resets_failures(self):
        supervisor = ServiceSupervisor(
            warning_threshold=2,
            critical_threshold=3,
        )

        supervisor.observe(
            {
                "status": "CRITICAL",
            }
        )
        result = supervisor.observe(
            {
                "status": "HEALTHY",
            }
        )

        self.assertEqual(
            result["action"],
            "CONTINUE",
        )
        self.assertEqual(
            result["consecutive_failures"],
            0,
        )

    def test_repeated_critical_requests_shutdown(self):
        supervisor = ServiceSupervisor(
            critical_threshold=2,
        )

        supervisor.observe(
            {
                "status": "CRITICAL",
            }
        )
        result = supervisor.observe(
            {
                "status": "CRITICAL",
            }
        )

        self.assertEqual(
            result["action"],
            "SHUTDOWN_REQUESTED",
        )


if __name__ == "__main__":
    unittest.main()
