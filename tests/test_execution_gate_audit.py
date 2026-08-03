from __future__ import annotations
import unittest
from app.diagnostics.execution_gate_audit import build_execution_gate_audit


class ExecutionGateAuditTests(unittest.TestCase):
    def test_separates_causal_and_cascaded_blocks(self):
        result = build_execution_gate_audit(
            final_decision={"decision": "HOLD"},
            validation={"allowed": False, "reason": "Decision is HOLD"},
            trade_quality={"passed": False, "primary_blockers": ["validation"]},
            confirmation={"passed": False, "decision": "REJECT"},
            risk_plan={"approved": False},
            trade_plan={"ready": False},
        )
        self.assertEqual(result["first_causal_blocker"], "Final decision is HOLD")
        self.assertTrue(result["causal_blockers"])
        self.assertTrue(result["cascaded_blockers"])
        self.assertTrue(result["diagnostics_only"])


if __name__ == "__main__":
    unittest.main()
