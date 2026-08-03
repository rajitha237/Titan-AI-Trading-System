"""Regression guard for the v26.1 NameError hotfix."""

from __future__ import annotations

import inspect
import unittest

from app.trader.auto_testnet_runner import (
    _evaluate_candidate_for_selection,
)


class DynamicRiskScopeRegressionTests(
    unittest.TestCase
):
    def test_candidate_evaluator_does_not_reference_selected_evaluation(
        self,
    ):
        source = inspect.getsource(
            _evaluate_candidate_for_selection
        )

        self.assertNotIn(
            "selected_evaluation",
            source,
        )


if __name__ == "__main__":
    unittest.main()
