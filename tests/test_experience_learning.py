"""Offline tests for TitanAI Experience Learning v1."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.learning import experience_store
from app.learning.experience_builder import build_experience_record
from app.learning.pattern_memory_engine import fingerprint_similarity
from app.learning.strategy_evolution_engine import (
    build_strategy_evolution_snapshot,
)


class ExperienceLearningTests(unittest.TestCase):
    def test_completed_trade_builds_stable_record(self):
        trade = {
            "trade_id": "trade-1",
            "symbol": "SOLUSDT",
            "side": "BUY",
            "entry_price": 100,
            "exit_price": 102,
            "net_pnl": 0.2,
            "outcome": "WIN",
            "opened_at": "2026-01-01T08:00:00+00:00",
            "closed_at": "2026-01-01T09:00:00+00:00",
            "duration_seconds": 3600,
            "metadata": {
                "last_position_state": {
                    "metadata": {
                        "candidate": {
                            "technical": {
                                "trend": "BULLISH",
                                "rsi": 55,
                                "adx": 30,
                                "macd_direction": "BUY",
                            },
                            "order_flow": {
                                "pressure": "AGGRESSIVE_BUYERS",
                                "delta_ratio": 0.3,
                            },
                            "order_book": {
                                "pressure": "BUY_PRESSURE",
                            },
                            "live_market_regime": {
                                "regime": "BULLISH_EXPANSION",
                            },
                            "institutional_strategy": {
                                "selected_strategy":
                                    "TREND_CONTINUATION",
                            },
                        }
                    }
                }
            },
        }

        record = build_experience_record(trade)
        self.assertEqual(record["symbol"], "SOLUSDT")
        self.assertEqual(record["side"], "BUY")
        self.assertEqual(record["outcome"], "WIN")
        self.assertEqual(
            record["pattern_fingerprint"]["strategy"],
            "TREND_CONTINUATION",
        )
        self.assertTrue(record["experience_id"].startswith("exp-"))

    def test_similarity_is_bounded(self):
        fingerprint = {
            "symbol": "SOLUSDT",
            "side": "BUY",
            "session": "LONDON",
            "market_regime": "BULLISH",
            "strategy": "TREND",
            "technical_trend": "BULLISH",
            "macd_direction": "BUY",
            "order_flow_pressure": "BUY",
            "order_book_pressure": "BUY",
            "research_decision": "SUPPORT",
            "rsi_bucket": 60,
            "adx_bucket": 30,
            "delta_bucket": 0.3,
        }
        score = fingerprint_similarity(fingerprint, fingerprint)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 1)
        self.assertAlmostEqual(score, 1.0, places=6)

    def test_store_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "experience.db"
            with patch.object(experience_store, "DB_PATH", db_path):
                record = {
                    "experience_id": "exp-test",
                    "trade_id": "trade-test",
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "outcome": "WIN",
                    "net_pnl": 1.0,
                    "pattern_fingerprint": {},
                    "context": {},
                }
                experience_store.save_experience(record)
                experience_store.save_experience(record)
                self.assertEqual(experience_store.count_experiences(), 1)


if __name__ == "__main__":
    unittest.main()
