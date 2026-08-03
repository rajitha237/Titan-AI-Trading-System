"""TitanAI SQLite trade journal and lightweight performance analytics."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "titanai_journal.db"
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if result == result and result not in (float("inf"), float("-inf")) else default
    except (TypeError, ValueError):
        return default


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        connection = sqlite3.connect(DB_PATH, timeout=15.0)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=15000")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    symbol TEXT,
                    decision TEXT,
                    execution_status TEXT,
                    execute_requested INTEGER NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0,
                    quantity REAL NOT NULL DEFAULT 0,
                    entry_price REAL NOT NULL DEFAULT 0,
                    average_fill_price REAL NOT NULL DEFAULT 0,
                    raw_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cycles_created_at ON cycles(created_at);
                CREATE INDEX IF NOT EXISTS idx_cycles_symbol ON cycles(symbol);

                CREATE TABLE IF NOT EXISTS trade_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    cycle_id INTEGER,
                    symbol TEXT,
                    event_type TEXT NOT NULL,
                    quantity REAL NOT NULL DEFAULT 0,
                    price REAL NOT NULL DEFAULT 0,
                    realised_pnl REAL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(cycle_id) REFERENCES cycles(id)
                );
                """
            )
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _extract_confidence(result: dict) -> float:
    confidence = result.get("confidence", {}) or {}
    for key in ("confidence", "score", "confidence_score", "percentage"):
        if key in confidence:
            return _float(confidence.get(key))
    return 0.0


def save_cycle_result(result: dict) -> int:
    """Persist one complete runner result and its important execution events."""
    execution = result.get("execution", {}) or {}
    final_decision = result.get("final_decision", {}) or {}
    trade_plan = result.get("trade_plan", {}) or {}
    verification = execution.get("verification", {}) or {}

    symbol = str(result.get("symbol", execution.get("symbol", ""))).upper() or None
    decision = str(final_decision.get("decision", execution.get("decision", "UNKNOWN"))).upper()
    execution_status = str(execution.get("status", "unknown")).lower()
    quantity = _float(execution.get("quantity", trade_plan.get("quantity", result.get("quantity", 0.0))))
    entry_price = _float(trade_plan.get("entry_price", result.get("price", 0.0)))
    fill_price = _float(execution.get("average_fill_price", verification.get("average_price", 0.0)))

    with _connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO cycles(
                created_at, status, symbol, decision, execution_status,
                execute_requested, confidence, quantity, entry_price,
                average_fill_price, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utc_now(), str(result.get("status", "unknown")), symbol, decision,
                execution_status, int(bool(result.get("execute_trade_requested", False))),
                _extract_confidence(result), quantity, entry_price, fill_price, _json(result),
            ),
        )
        cycle_id = int(cursor.lastrowid)

        if execution_status in {"protected", "verified_filled", "filled"}:
            connection.execute(
                """INSERT INTO trade_events(created_at, cycle_id, symbol, event_type, quantity, price, payload)
                   VALUES (?, ?, ?, 'ENTRY_FILLED', ?, ?, ?)""",
                (_utc_now(), cycle_id, symbol, quantity, fill_price or entry_price, _json(execution)),
            )

        for manager_key, event_type in (
            ("partial_take_profit_manager", "PARTIAL_TP"),
            ("break_even_manager", "BREAK_EVEN"),
            ("trailing_stop_manager", "TRAILING_STOP"),
        ):
            manager = result.get(manager_key, {}) or {}
            for item in manager.get("results", []) or []:
                if not isinstance(item, dict):
                    continue
                happened = (
                    item.get("executed") is True
                    or item.get("moved") is True
                    or str(item.get("status", "")).lower() in {"executed", "moved", "activated", "updated"}
                )
                if happened:
                    connection.execute(
                        """INSERT INTO trade_events(created_at, cycle_id, symbol, event_type, quantity, price, payload)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            _utc_now(), cycle_id, str(item.get("symbol", symbol or "")).upper(), event_type,
                            _float(item.get("closed_quantity", item.get("current_quantity", 0.0))),
                            _float(item.get("mark_price", item.get("execution_price", 0.0))), _json(item),
                        ),
                    )
    return cycle_id


def record_trade_event(
    event_type: str,
    *,
    symbol: str,
    quantity: float = 0.0,
    price: float = 0.0,
    realised_pnl: float | None = None,
    payload: dict | None = None,
    cycle_id: int | None = None,
) -> int:
    with _connection() as connection:
        cursor = connection.execute(
            """INSERT INTO trade_events(
                   created_at, cycle_id, symbol, event_type, quantity, price, realised_pnl, payload
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _utc_now(), cycle_id, symbol.upper(), event_type.upper(), _float(quantity),
                _float(price), None if realised_pnl is None else _float(realised_pnl), _json(payload or {}),
            ),
        )
        return int(cursor.lastrowid)


def get_recent_cycles(limit: int = 20) -> list[dict]:
    safe_limit = max(1, min(int(limit), 500))
    with _connection() as connection:
        rows = connection.execute(
            "SELECT * FROM cycles ORDER BY id DESC LIMIT ?", (safe_limit,)
        ).fetchall()
    return [
        {
            "id": row["id"], "created_at": row["created_at"], "status": row["status"],
            "symbol": row["symbol"], "decision": row["decision"],
            "execution_status": row["execution_status"], "execute_requested": bool(row["execute_requested"]),
            "confidence": row["confidence"], "quantity": row["quantity"],
            "entry_price": row["entry_price"], "average_fill_price": row["average_fill_price"],
        }
        for row in rows
    ]


def get_performance_summary() -> dict:
    """Return journal health and realised-PnL statistics when available."""
    with _connection() as connection:
        cycles = connection.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN execution_status='protected' THEN 1 ELSE 0 END) AS protected,
                      SUM(CASE WHEN execution_status='blocked' THEN 1 ELSE 0 END) AS blocked,
                      SUM(CASE WHEN execution_status='skipped' THEN 1 ELSE 0 END) AS skipped
               FROM cycles"""
        ).fetchone()
        pnl = connection.execute(
            """SELECT COUNT(realised_pnl) AS closed_events,
                      COALESCE(SUM(realised_pnl), 0) AS total_pnl,
                      COALESCE(AVG(realised_pnl), 0) AS average_pnl,
                      SUM(CASE WHEN realised_pnl > 0 THEN 1 ELSE 0 END) AS wins,
                      SUM(CASE WHEN realised_pnl < 0 THEN 1 ELSE 0 END) AS losses
               FROM trade_events WHERE realised_pnl IS NOT NULL"""
        ).fetchone()

    closed = int(pnl["closed_events"] or 0)
    wins = int(pnl["wins"] or 0)
    return {
        "database": str(DB_PATH),
        "total_cycles": int(cycles["total"] or 0),
        "protected_entries": int(cycles["protected"] or 0),
        "blocked_cycles": int(cycles["blocked"] or 0),
        "skipped_cycles": int(cycles["skipped"] or 0),
        "closed_pnl_events": closed,
        "wins": wins,
        "losses": int(pnl["losses"] or 0),
        "win_rate": round((wins / closed * 100.0), 2) if closed else 0.0,
        "total_realised_pnl": round(_float(pnl["total_pnl"]), 8),
        "average_realised_pnl": round(_float(pnl["average_pnl"]), 8),
    }