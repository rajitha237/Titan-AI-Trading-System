"""Autonomous service safety tests."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.service.autonomous_runner import (
    AutonomousServiceConfig,
    run_autonomous_service,
)


class AutonomousServiceTests(
    unittest.TestCase
):
    def test_default_mode_is_analysis_only(self):
        config = (
            AutonomousServiceConfig()
            .normalized()
        )

        self.assertFalse(
            config.execute_trade
        )
        self.assertGreaterEqual(
            config.interval_seconds,
            30.0,
        )

    def test_bounded_service_never_submits_in_analysis_mode(self):
        fake_result = {
            "status": "skipped",
            "mode": "ANALYSIS_ONLY",
            "execution": {
                "status": "skipped",
                "submitted": False,
            },
        }

        with (
            patch(
                "app.service.autonomous_runner."
                "run_auto_testnet_cycle",
                new=AsyncMock(
                    return_value=fake_result
                ),
            ) as runner_mock,
            patch(
                "app.service.autonomous_runner."
                "write_heartbeat",
                return_value={},
            ),
            patch(
                "app.service.autonomous_runner."
                "_append_cycle_log",
                return_value=None,
            ),
        ):
            result = asyncio.run(
                run_autonomous_service(
                    AutonomousServiceConfig(
                        maximum_cycles=1,
                    )
                )
            )

        self.assertEqual(
            result["cycles_completed"],
            1,
        )
        self.assertFalse(
            result["execute_trade"]
        )

        runner_mock.assert_awaited_once()

        self.assertFalse(
            runner_mock.await_args.kwargs[
                "execute_trade"
            ]
        )

    def test_explicit_testnet_execution_flag_is_forwarded(self):
        fake_result = {
            "status": "skipped",
            "mode": "NO_EXECUTABLE_CANDIDATE",
            "execution": {
                "status": "skipped",
                "submitted": False,
            },
        }

        with (
            patch(
                "app.service.autonomous_runner."
                "run_auto_testnet_cycle",
                new=AsyncMock(
                    return_value=fake_result
                ),
            ) as runner_mock,
            patch(
                "app.service.autonomous_runner."
                "write_heartbeat",
                return_value={},
            ),
            patch(
                "app.service.autonomous_runner."
                "_append_cycle_log",
                return_value=None,
            ),
        ):
            asyncio.run(
                run_autonomous_service(
                    AutonomousServiceConfig(
                        execute_trade=True,
                        maximum_cycles=1,
                    )
                )
            )

        self.assertTrue(
            runner_mock.await_args.kwargs[
                "execute_trade"
            ]
        )


if __name__ == "__main__":
    unittest.main()
