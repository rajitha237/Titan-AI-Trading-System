from __future__ import annotations
import unittest
from app.notifications.notification_router import (
    derive_notifications,
    route_notifications,
)


class NotificationRouterTests(unittest.TestCase):
    def test_watchdog_block_creates_alert(self):
        events = derive_notifications({
            "cycle_id": "abc",
            "execution_watchdog": {
                "allowed": False,
                "block_reasons": ["exchange unavailable"],
            },
        })
        self.assertEqual(events[0]["event_type"], "WATCHDOG_BLOCKED")

    def test_delivery_failure_is_non_blocking(self):
        result = route_notifications(
            {"status": "error", "reason": "failure"},
            history_function=lambda *args, **kwargs: {
                "notification_id": 1,
            },
            telegram_function=lambda notification: {
                "status": "failed",
                "sent": False,
            },
        )
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["non_blocking"])


if __name__ == "__main__":
    unittest.main()
