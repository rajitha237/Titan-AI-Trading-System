from __future__ import annotations
import unittest
from app.dashboard.system_dashboard import build_system_dashboard


class SystemDashboardTests(unittest.TestCase):
    def test_all_sections_are_exposed(self):
        dashboard = build_system_dashboard({
            "status": "skipped",
            "mode": "ANALYSIS_ONLY",
            "live_position_sync": {"status": "success", "audit_after": {"status": "consistent"}},
            "order_recovery": {"status": "success", "audit_after": {"status": "consistent"}},
            "execution_watchdog": {
                "status": "ready",
                "allowed": True,
                "exchange_health": {"status": "healthy", "healthy": True},
            },
            "execution": {"status": "skipped", "submitted": False},
        })
        for key in (
            "system", "exchange", "watchdog", "service", "positions",
            "orders", "risk", "ai", "learning", "execution",
        ):
            self.assertIn(key, dashboard)
        self.assertTrue(dashboard["read_only"])

    def test_blocked_state_is_critical(self):
        dashboard = build_system_dashboard({
            "status": "blocked",
            "live_position_sync": {"status": "blocked"},
            "order_recovery": {"status": "blocked"},
            "execution_watchdog": {"status": "blocked"},
        })
        self.assertEqual(dashboard["overall_health"], "critical")


if __name__ == "__main__":
    unittest.main()
