from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.notifications import notification_history
from app.notifications.notification_history import (
    count_notifications,
    save_notification,
)
from app.notifications.notification_models import build_notification


class NotificationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patch = patch.object(
            notification_history,
            "DB_PATH",
            Path(self.temp_dir.name) / "notifications.db",
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp_dir.cleanup()

    def test_save_is_idempotent(self):
        notification = build_notification(
            event_type="SYSTEM_ERROR",
            severity="CRITICAL",
            title="Error",
            message="Failure",
            cycle_id="cycle-1",
        )
        for _ in range(2):
            save_notification(
                notification,
                delivery_status="stored_only",
                telegram_status="disabled",
            )
        self.assertEqual(count_notifications(), 1)


if __name__ == "__main__":
    unittest.main()
