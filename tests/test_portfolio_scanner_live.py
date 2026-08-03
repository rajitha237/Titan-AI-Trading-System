"""Live public-market smoke test for the institutional scanner."""

from __future__ import annotations

import asyncio
import os
import unittest

from app.trader.portfolio_scanner import scan_portfolio


@unittest.skipUnless(
    os.getenv("TITANAI_RUN_LIVE_TESTS") == "1",
    "Set TITANAI_RUN_LIVE_TESTS=1 to run Binance live-data tests",
)
class PortfolioScannerLiveTests(unittest.TestCase):
    def test_scanner_schema(self):
        result = asyncio.run(
            scan_portfolio(
                limit=3,
                maximum_position_usdt=7.5,
            )
        )
        self.assertEqual(result.get("status"), "success")
        self.assertEqual(
            result.get("selection_mode"),
            "INSTITUTIONAL_ADAPTIVE_SCORE_THEN_EXECUTABLE",
        )
        self.assertIsInstance(result.get("ranked"), list)

        for item in result.get("ranked", []):
            self.assertIn("symbol", item)
            self.assertIn("adaptive_score", item)
            self.assertIn("live_market_regime", item)
            self.assertIn("institutional_strategy", item)
            self.assertIn("institutional_probability", item)
            self.assertIn("research_confluence", item)


if __name__ == "__main__":
    unittest.main()
