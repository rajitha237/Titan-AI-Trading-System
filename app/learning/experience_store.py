"""SQLite store for completed-trade experience records."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "titanai_experience.db"
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
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
                CREATE TABLE IF NOT EXISTS experiences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experience_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    trade_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    net_pnl REAL NOT NULL DEFAULT 0,
                    strategy TEXT,
                    market_regime TEXT,
                    session TEXT,
                    entry_price REAL NOT NULL DEFAULT 0,
                    exit_price REAL NOT NULL DEFAULT 0,
                    duration_seconds REAL NOT NULL DEFAULT 0,
                    ai_score REAL NOT NULL DEFAULT 0,
                    confirmation_score REAL NOT NULL DEFAULT 0,
                    fingerprint_json TEXT NOT NULL DEFAULT '{}',
                    context_json TEXT NOT NULL DEFAULT '{}',
                    raw_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_experience_symbol
                ON experiences(symbol);

                CREATE INDEX IF NOT EXISTS idx_experience_side
                ON experiences(side);

                CREATE INDEX IF NOT EXISTS idx_experience_strategy
                ON experiences(strategy);

                CREATE INDEX IF NOT EXISTS idx_experience_regime
                ON experiences(market_regime);

                CREATE INDEX IF NOT EXISTS idx_experience_session
                ON experiences(session);

                CREATE INDEX IF NOT EXISTS idx_experience_created_at
                ON experiences(created_at);
                """
            )

            yield connection
            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()


def save_experience(record: dict) -> dict:
    """Insert one idempotent completed-trade experience."""
    experience_id = str(record.get("experience_id", "")).strip()
    symbol = str(record.get("symbol", "")).upper().strip()
    side = str(record.get("side", "")).upper().strip()
    outcome = str(record.get("outcome", "BREAKEVEN")).upper().strip()

    if not experience_id:
        raise ValueError("experience_id is required")
    if not symbol:
        raise ValueError("symbol is required")
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")

    with _connection() as connection:
        connection.execute(
            """
            INSERT INTO experiences(
                experience_id,
                created_at,
                trade_id,
                symbol,
                side,
                outcome,
                net_pnl,
                strategy,
                market_regime,
                session,
                entry_price,
                exit_price,
                duration_seconds,
                ai_score,
                confirmation_score,
                fingerprint_json,
                context_json,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(experience_id)
            DO UPDATE SET
                outcome = excluded.outcome,
                net_pnl = excluded.net_pnl,
                strategy = excluded.strategy,
                market_regime = excluded.market_regime,
                session = excluded.session,
                exit_price = excluded.exit_price,
                duration_seconds = excluded.duration_seconds,
                ai_score = excluded.ai_score,
                confirmation_score = excluded.confirmation_score,
                fingerprint_json = excluded.fingerprint_json,
                context_json = excluded.context_json,
                raw_json = excluded.raw_json
            """,
            (
                experience_id,
                str(record.get("created_at") or _utc_now()),
                record.get("trade_id"),
                symbol,
                side,
                outcome,
                float(record.get("net_pnl", 0.0) or 0.0),
                record.get("strategy"),
                record.get("market_regime"),
                record.get("session"),
                float(record.get("entry_price", 0.0) or 0.0),
                float(record.get("exit_price", 0.0) or 0.0),
                float(record.get("duration_seconds", 0.0) or 0.0),
                float(record.get("ai_score", 0.0) or 0.0),
                float(record.get("confirmation_score", 0.0) or 0.0),
                _json(record.get("pattern_fingerprint") or {}),
                _json(record.get("context") or {}),
                _json(record),
            ),
        )

    return {
        "status": "saved",
        "experience_id": experience_id,
        "database": str(DB_PATH),
    }


def list_experiences(
    *,
    symbol: str | None = None,
    side: str | None = None,
    strategy: str | None = None,
    market_regime: str | None = None,
    session: str | None = None,
    limit: int = 5000,
) -> list[dict]:
    clauses: list[str] = []
    parameters: list[Any] = []

    for column, value in (
        ("symbol", symbol.upper() if symbol else None),
        ("side", side.upper() if side else None),
        ("strategy", strategy),
        ("market_regime", market_regime),
        ("session", session),
    ):
        if value:
            clauses.append(f"{column} = ?")
            parameters.append(value)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    safe_limit = max(1, min(int(limit), 10000))
    parameters.append(safe_limit)

    with _connection() as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM experiences
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            parameters,
        ).fetchall()

    return [
        {
            **dict(row),
            "pattern_fingerprint": _loads(
                row["fingerprint_json"],
                {},
            ),
            "context": _loads(row["context_json"], {}),
            "raw": _loads(row["raw_json"], {}),
        }
        for row in rows
    ]


def count_experiences() -> int:
    with _connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM experiences"
        ).fetchone()
    return int(row["count"] if row else 0)
