"""Research Engine v2 SQLite result store."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


STRATEGY_NAME = "CONFLUENCE_SK_V2"


@contextmanager
def _connection(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path, timeout=15.0)
    connection.row_factory = sqlite3.Row

    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=15000")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS research_results_v2 (
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                approved INTEGER NOT NULL,
                test_trade_count INTEGER NOT NULL,
                test_win_rate_percent REAL NOT NULL,
                test_profit_factor REAL NOT NULL,
                test_expectancy_r REAL NOT NULL,
                test_maximum_drawdown_percent REAL NOT NULL,
                report_json TEXT NOT NULL,
                PRIMARY KEY(symbol, timeframe, strategy_name)
            )
            """
        )

        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def save_report(
    database_path: Path,
    report: dict,
    *,
    strategy_name: str = STRATEGY_NAME,
) -> None:
    test = report.get("test_report", {})

    with _connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO research_results_v2(
                symbol,
                timeframe,
                strategy_name,
                updated_at,
                approved,
                test_trade_count,
                test_win_rate_percent,
                test_profit_factor,
                test_expectancy_r,
                test_maximum_drawdown_percent,
                report_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, timeframe, strategy_name)
            DO UPDATE SET
                updated_at = excluded.updated_at,
                approved = excluded.approved,
                test_trade_count = excluded.test_trade_count,
                test_win_rate_percent = excluded.test_win_rate_percent,
                test_profit_factor = excluded.test_profit_factor,
                test_expectancy_r = excluded.test_expectancy_r,
                test_maximum_drawdown_percent =
                    excluded.test_maximum_drawdown_percent,
                report_json = excluded.report_json
            """,
            (
                report["symbol"],
                report["timeframe"],
                strategy_name,
                datetime.now(timezone.utc).isoformat(),
                int(bool(report.get("approved"))),
                int(test.get("trade_count", 0)),
                float(test.get("win_rate_percent", 0.0)),
                float(test.get("profit_factor", 0.0)),
                float(test.get("expectancy_r", 0.0)),
                float(
                    test.get(
                        "maximum_drawdown_percent",
                        0.0,
                    )
                ),
                json.dumps(report, default=str),
            ),
        )


def get_report(
    database_path: Path,
    symbol: str,
    timeframe: str,
    *,
    strategy_name: str = STRATEGY_NAME,
) -> dict | None:
    with _connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT report_json
            FROM research_results_v2
            WHERE symbol = ?
              AND timeframe = ?
              AND strategy_name = ?
            """,
            (
                symbol.upper(),
                timeframe,
                strategy_name,
            ),
        ).fetchone()

    return json.loads(row["report_json"]) if row else None


def list_reports(database_path: Path) -> list[dict]:
    with _connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT report_json
            FROM research_results_v2
            ORDER BY
                approved DESC,
                test_expectancy_r DESC,
                test_profit_factor DESC
            """
        ).fetchall()

    return [
        json.loads(row["report_json"])
        for row in rows
    ]
