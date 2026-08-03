"""Live Position Synchronizer v27 tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.trader import persistent_trade_state
from app.trader.live_position_synchronizer import (
    build_position_consistency_audit,
    synchronise_live_positions,
)


def exchange_position(
    *,
    symbol: str = "BTCUSDT",
    amount: str = "0.001",
    entry: str = "60000",
    mark: str = "60500",
) -> dict:
    return {
        "symbol": symbol,
        "positionAmt": amount,
        "entryPrice": entry,
        "markPrice": mark,
    }


class LivePositionSynchronizerTests(
    unittest.TestCase
):
    def setUp(self):
        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )
        self.db_path = (
            Path(self.temp_dir.name)
            / "state.db"
        )
        self.patch = patch.object(
            persistent_trade_state,
            "DB_PATH",
            self.db_path,
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp_dir.cleanup()

    def test_restart_recovers_missing_local_state(self):
        result = synchronise_live_positions(
            exchange_positions=[
                exchange_position()
            ],
            reconcile_function=lambda positions: {
                "status": "success",
                "closed_positions_detected": 0,
                "completed_trades": [],
                "errors": [],
            },
        )

        self.assertEqual(
            result["status"],
            "success",
        )
        self.assertEqual(
            result["audit_before"][
                "missing_local_states"
            ],
            [
                {
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                }
            ],
        )
        self.assertEqual(
            result["audit_after"][
                "status"
            ],
            "consistent",
        )
        self.assertFalse(
            result["execution_submitted"]
        )

    def test_invalid_exchange_snapshot_never_mutates_state(self):
        result = synchronise_live_positions(
            exchange_positions=None,
        )

        self.assertEqual(
            result["status"],
            "blocked",
        )
        self.assertFalse(
            result["mutation_performed"]
        )

    def test_audit_detects_quantity_drift(self):
        audit = build_position_consistency_audit(
            exchange_positions=[
                exchange_position(
                    amount="0.002"
                )
            ],
            local_open_states=[
                {
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "status": "OPEN",
                    "entry_price": 60000.0,
                    "current_quantity": 0.001,
                }
            ],
        )

        self.assertEqual(
            audit["status"],
            "drift_detected",
        )
        self.assertEqual(
            len(
                audit[
                    "quantity_mismatches"
                ]
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
