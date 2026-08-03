from __future__ import annotations
import os
import unittest
from unittest.mock import patch
from app.notifications.telegram_notifier import send_telegram_notification


class TelegramNotifierTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            result = send_telegram_notification({
                "severity": "INFO",
                "title": "Test",
                "message": "Test",
            })
        self.assertEqual(result["status"], "disabled")
        self.assertFalse(result["sent"])


if __name__ == "__main__":
    unittest.main()
