from __future__ import annotations
import unittest
from app.notifications.alert_formatter import format_alert


class AlertFormatterTests(unittest.TestCase):
    def test_formats_critical_alert(self):
        text = format_alert({
            "severity": "CRITICAL",
            "title": "Watchdog",
            "message": "Blocked",
            "cycle_id": "abc",
        })
        self.assertIn("TitanAI", text)
        self.assertIn("Blocked", text)


if __name__ == "__main__":
    unittest.main()
