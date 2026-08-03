"""Regression tests for TitanAI warning cleanup."""

from __future__ import annotations

import inspect
import unittest

import app.services.liquidity_tracker as liquidity_tracker
import app.services.whale_engine as whale_engine
import app.trader.persistent_trade_state as persistent_trade_state
import app.trader.trade_journal as trade_journal


class WarningCleanupTests(unittest.TestCase):
    def test_no_datetime_utcnow_in_services(self):
        liquidity_source = inspect.getsource(liquidity_tracker)
        whale_source = inspect.getsource(whale_engine)

        self.assertNotIn("datetime.utcnow(", liquidity_source)
        self.assertNotIn("datetime.utcnow(", whale_source)
        self.assertIn("datetime.now(timezone.utc)", liquidity_source)
        self.assertIn("datetime.now(timezone.utc)", whale_source)

    def test_sqlite_context_managers_close_connections(self):
        state_source = inspect.getsource(
            persistent_trade_state._connection
        )
        journal_source = inspect.getsource(
            trade_journal._connection
        )

        self.assertIn("finally:", state_source)
        self.assertIn("connection.close()", state_source)
        self.assertIn("finally:", journal_source)
        self.assertIn("connection.close()", journal_source)


if __name__ == "__main__":
    unittest.main()
