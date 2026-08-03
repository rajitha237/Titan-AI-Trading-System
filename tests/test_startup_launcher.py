from __future__ import annotations
import asyncio
import unittest
from unittest.mock import patch
from app.operations.startup_launcher import launch_once


class StartupLauncherTests(unittest.TestCase):
    def test_blocked_startup_never_runs_runner(self):
        with (
            patch("app.operations.startup_launcher.evaluate_startup_readiness",
                  return_value={"startup_allowed": False}),
            patch("app.operations.startup_launcher.run_auto_testnet_cycle") as runner,
        ):
            result = asyncio.run(launch_once(execute_trade=True))
        runner.assert_not_called()
        self.assertEqual(result["status"], "blocked")

    def test_ready_launcher_runs_one_cycle(self):
        with (
            patch("app.operations.startup_launcher.evaluate_startup_readiness",
                  return_value={"startup_allowed": True}),
            patch("app.operations.startup_launcher.build_production_readiness_report",
                  return_value={"ready": True}),
            patch("app.operations.startup_launcher.run_auto_testnet_cycle",
                  return_value={"status": "skipped", "execution": {"submitted": False}}),
        ):
            result = asyncio.run(launch_once(execute_trade=False))
        self.assertEqual(result["launcher"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
