from __future__ import annotations
import unittest
from app.dashboard.dashboard_models import safe_float, section


class DashboardModelsTests(unittest.TestCase):
    def test_safe_float_rejects_nan(self):
        self.assertEqual(safe_float(float("nan"), 3.0), 3.0)

    def test_section_schema(self):
        result = section("READY", "ok", {"value": 1})
        self.assertEqual(result["status"], "ready")
        self.assertIn("warnings", result)


if __name__ == "__main__":
    unittest.main()
