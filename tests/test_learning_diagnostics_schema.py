"""Schema tests for runner learning diagnostics."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.learning.learning_diagnostics import (
    build_runner_learning_diagnostics,
)


class LearningDiagnosticsSchemaTests(
    unittest.TestCase
):
    def test_candidate_learning_is_exposed(self):
        result = {
            "symbol": "SOLUSDT",
            "execution": {
                "submitted": False,
            },
            "scan": {
                "best_setup": {
                    "symbol": "SOLUSDT",
                    "pattern_memory": {
                        "sample_size": 12,
                        "confidence_adjustment": 4.0,
                    },
                    "self_learning": {
                        "learning_adjustment": 1.5,
                        "symbol_evidence": {
                            "sample_size": 12,
                        },
                    },
                }
            },
        }

        with patch(
            "app.learning.learning_diagnostics."
            "build_self_learning_dashboard",
            return_value={
                "status": "success",
                "overall": {
                    "trade_count": 12,
                },
            },
        ):
            diagnostics = (
                build_runner_learning_diagnostics(
                    result
                )
            )

        self.assertTrue(
            diagnostics["diagnostics_only"]
        )
        self.assertEqual(
            diagnostics["learning_status"],
            "SUPPORT",
        )
        self.assertEqual(
            diagnostics["learning_adjustment"],
            1.5,
        )
        self.assertEqual(
            diagnostics["pattern_adjustment"],
            4.0,
        )
        self.assertFalse(
            diagnostics["execution_submitted"]
        )

    def test_empty_result_is_safe(self):
        diagnostics = (
            build_runner_learning_diagnostics({})
        )

        self.assertEqual(
            diagnostics["learning_adjustment"],
            0.0,
        )
        self.assertIn(
            diagnostics["learning_status"],
            {
                "INSUFFICIENT_SAMPLE",
                "NEUTRAL",
            },
        )


if __name__ == "__main__":
    unittest.main()
