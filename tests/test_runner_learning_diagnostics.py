"""Analysis-only integration test for runner learning diagnostics."""

from __future__ import annotations

import asyncio
import os
import unittest

from app.trader.auto_testnet_runner import (
    run_auto_testnet_cycle,
)


@unittest.skipUnless(
    os.getenv("TITANAI_RUN_PIPELINE_TESTS") == "1",
    "Set TITANAI_RUN_PIPELINE_TESTS=1 to run analysis-only runner test",
)
class RunnerLearningDiagnosticsTests(
    unittest.TestCase
):
    def test_analysis_only_runner_exposes_diagnostics(self):
        result = asyncio.run(
            run_auto_testnet_cycle(
                execute_trade=False,
                scan_limit=5,
            )
        )

        self.assertIn(
            "learning_diagnostics",
            result,
        )
        self.assertIn(
            "learning_dashboard",
            result,
        )
        self.assertIn(
            "learning_adjustment",
            result,
        )
        self.assertIn(
            "learning_status",
            result,
        )
        self.assertIn(
            "pattern_memory",
            result,
        )
        self.assertIn(
            "self_learning",
            result,
        )

        diagnostics = result[
            "learning_diagnostics"
        ]

        self.assertTrue(
            diagnostics.get(
                "diagnostics_only"
            )
        )
        self.assertFalse(
            result.get(
                "execution",
                {},
            ).get(
                "submitted",
                False,
            )
        )


if __name__ == "__main__":
    unittest.main()
