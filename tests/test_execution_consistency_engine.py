from __future__ import annotations
import unittest
from app.trader.execution_consistency_engine import evaluate_execution_consistency


class ExecutionConsistencyTests(unittest.TestCase):
    def test_filled_execution_is_consistent(self):
        result = evaluate_execution_consistency({
            "status": "success",
            "submitted": True,
            "quantity": 1.0,
            "verification": {
                "verified": True,
                "filled": True,
                "order_status": "FILLED",
                "filled_quantity": 1.0,
                "average_price": 100.0,
            },
        })
        self.assertTrue(result["consistent"])

    def test_unverified_submission_is_inconsistent(self):
        result = evaluate_execution_consistency({
            "submitted": True,
            "verification": {"verified": False},
        })
        self.assertFalse(result["consistent"])


if __name__ == "__main__":
    unittest.main()
