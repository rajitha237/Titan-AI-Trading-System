from __future__ import annotations
import unittest
from app.dashboard.dashboard_formatter import format_dashboard_summary


class DashboardFormatterTests(unittest.TestCase):
    def test_compact_summary(self):
        text = format_dashboard_summary({
            "overall_health": "healthy",
            "system": {"data": {"mode": "ANALYSIS_ONLY"}},
            "exchange": {"status": "healthy"},
            "watchdog": {"status": "ready"},
            "execution": {"status": "skipped", "data": {"submitted": False}},
        })
        self.assertIn("health=healthy", text)
        self.assertIn("submitted=False", text)


if __name__ == "__main__":
    unittest.main()
