import sqlite3
from pathlib import Path
from app.analytics.service import AnalyticsService

def test_snapshot_metrics(tmp_path: Path) -> None:
    db = tmp_path / "journal.db"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE trade_events (id INTEGER PRIMARY KEY, created_at TEXT, cycle_id INTEGER, symbol TEXT, event_type TEXT, realised_pnl REAL)")
        con.executemany("INSERT INTO trade_events(created_at, cycle_id, symbol, event_type, realised_pnl) VALUES(?,?,?,?,?)", [
            ("2026-07-20T10:00:00+00:00", 1, "BTCUSDT", "CLOSE", 5.0),
            ("2026-07-21T10:00:00+00:00", 2, "ETHUSDT", "CLOSE", -2.0),
            ("2026-07-21T11:00:00+00:00", 3, "BTCUSDT", "CLOSE", 3.0),
        ])
    data = AnalyticsService(db).snapshot(); summary = data["summary"]
    assert summary["closed_trades"] == 3
    assert summary["wins"] == 2 and summary["losses"] == 1
    assert summary["total_realised_pnl"] == 6.0
    assert summary["profit_factor"] == 4.0
    assert summary["max_drawdown"] == 2.0
    assert len(data["daily_pnl"]) == 2
