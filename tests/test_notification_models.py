from __future__ import annotations
import unittest
from app.notifications.notification_models import build_notification


class NotificationModelsTests(unittest.TestCase):
    def test_builds_stable_event_key(self):
        first = build_notification(
            event_type="SYSTEM_ERROR",
            severity="CRITICAL",
            title="Error",
            message="Failure",
            cycle_id="cycle-1",
            data={"x": 1},
        )
        second = build_notification(
            event_type="SYSTEM_ERROR",
            severity="CRITICAL",
            title="Error",
            message="Failure",
            cycle_id="cycle-1",
            data={"x": 1},
        )
        self.assertEqual(first["event_key"], second["event_key"])

    def test_invalid_severity_is_rejected(self):
        with self.assertRaises(ValueError):
            build_notification(
                event_type="SYSTEM_ERROR",
                severity="LOW",
                title="Error",
                message="Failure",
            )


if __name__ == "__main__":
    unittest.main()
