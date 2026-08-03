"""SQLite-backed local order recovery state v28."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "titanai_order_recovery.db"
)
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(timespec="milliseconds")


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _loads(
    value: str | None,
    default: Any,
) -> Any:
    if not value:
        return default

    try:
        return json.loads(value)
    except (
        TypeError,
        json.JSONDecodeError,
    ):
        return default


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with _LOCK:
        connection = sqlite3.connect(
            DB_PATH,
            timeout=15.0,
        )
        connection.row_factory = sqlite3.Row

        try:
            connection.execute(
                "PRAGMA journal_mode=WAL"
            )
            connection.execute(
                "PRAGMA busy_timeout=15000"
            )
            _initialise(connection)
            yield connection
            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()


def _initialise(
    connection: sqlite3.Connection,
) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS order_recovery_state (
            order_key TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            order_id TEXT,
            client_order_id TEXT,
            order_type TEXT NOT NULL,
            side TEXT NOT NULL,
            status TEXT NOT NULL,
            reduce_only INTEGER NOT NULL DEFAULT 0,
            is_algo_order INTEGER NOT NULL DEFAULT 0,
            quantity REAL NOT NULL DEFAULT 0,
            price REAL NOT NULL DEFAULT 0,
            stop_price REAL NOT NULL DEFAULT 0,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            disappeared_at TEXT,
            metadata TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS
        idx_order_recovery_symbol_status
        ON order_recovery_state(symbol, status);
        """
    )


def _row_to_state(
    row: sqlite3.Row,
) -> dict:
    return {
        "order_key": row["order_key"],
        "symbol": row["symbol"],
        "order_id": row["order_id"],
        "client_order_id": (
            row["client_order_id"]
        ),
        "order_type": row["order_type"],
        "side": row["side"],
        "status": row["status"],
        "reduce_only": bool(
            row["reduce_only"]
        ),
        "is_algo_order": bool(
            row["is_algo_order"]
        ),
        "quantity": row["quantity"],
        "price": row["price"],
        "stop_price": row["stop_price"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "disappeared_at": row["disappeared_at"],
        "metadata": _loads(
            row["metadata"],
            {},
        ),
    }


def upsert_open_order(
    order: dict,
) -> dict:
    now = _utc_now()
    order_key = str(
        order.get("order_key", "")
    )

    if not order_key:
        raise ValueError(
            "Normalised order_key is required"
        )

    with _connection() as connection:
        existing = connection.execute(
            """
            SELECT first_seen_at, metadata
            FROM order_recovery_state
            WHERE order_key = ?
            """,
            (order_key,),
        ).fetchone()

        first_seen_at = (
            existing["first_seen_at"]
            if existing
            else now
        )
        metadata = (
            _loads(
                existing["metadata"],
                {},
            )
            if existing
            else {}
        )
        metadata.update(
            order.get("metadata") or {}
        )

        connection.execute(
            """
            INSERT INTO order_recovery_state(
                order_key,
                symbol,
                order_id,
                client_order_id,
                order_type,
                side,
                status,
                reduce_only,
                is_algo_order,
                quantity,
                price,
                stop_price,
                first_seen_at,
                last_seen_at,
                disappeared_at,
                metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, 'OPEN',
                    ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            ON CONFLICT(order_key) DO UPDATE SET
                symbol = excluded.symbol,
                order_id = excluded.order_id,
                client_order_id =
                    excluded.client_order_id,
                order_type = excluded.order_type,
                side = excluded.side,
                status = 'OPEN',
                reduce_only = excluded.reduce_only,
                is_algo_order =
                    excluded.is_algo_order,
                quantity = excluded.quantity,
                price = excluded.price,
                stop_price = excluded.stop_price,
                last_seen_at =
                    excluded.last_seen_at,
                disappeared_at = NULL,
                metadata = excluded.metadata
            """,
            (
                order_key,
                order.get("symbol"),
                str(
                    order.get("order_id")
                    or ""
                ),
                str(
                    order.get(
                        "client_order_id"
                    )
                    or ""
                ),
                order.get("order_type"),
                order.get("side"),
                int(
                    bool(
                        order.get(
                            "reduce_only"
                        )
                    )
                ),
                int(
                    bool(
                        order.get(
                            "is_algo_order"
                        )
                    )
                ),
                float(
                    order.get("quantity", 0.0)
                ),
                float(
                    order.get("price", 0.0)
                ),
                float(
                    order.get(
                        "stop_price",
                        0.0,
                    )
                ),
                first_seen_at,
                now,
                _json(metadata),
            ),
        )

    return get_order_state(
        order_key
    ) or {}


def mark_disappeared_orders(
    active_order_keys: set[str],
) -> list[dict]:
    now = _utc_now()

    with _connection() as connection:
        rows = connection.execute(
            """
            SELECT order_key
            FROM order_recovery_state
            WHERE status = 'OPEN'
            """
        ).fetchall()

        disappeared = [
            str(row["order_key"])
            for row in rows
            if str(row["order_key"])
            not in active_order_keys
        ]

        for order_key in disappeared:
            connection.execute(
                """
                UPDATE order_recovery_state
                SET status =
                        'MISSING_FROM_EXCHANGE',
                    disappeared_at = ?,
                    last_seen_at = ?
                WHERE order_key = ?
                """,
                (
                    now,
                    now,
                    order_key,
                ),
            )

    return [
        get_order_state(order_key) or {}
        for order_key in disappeared
    ]


def get_order_state(
    order_key: str,
) -> dict | None:
    with _connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM order_recovery_state
            WHERE order_key = ?
            """,
            (str(order_key),),
        ).fetchone()

    return (
        _row_to_state(row)
        if row
        else None
    )


def list_order_states(
    status: str | None = None,
) -> list[dict]:
    query = (
        "SELECT * "
        "FROM order_recovery_state"
    )
    params: list[Any] = []

    if status:
        query += " WHERE status = ?"
        params.append(
            str(status).upper()
        )

    query += " ORDER BY last_seen_at DESC"

    with _connection() as connection:
        rows = connection.execute(
            query,
            params,
        ).fetchall()

    return [
        _row_to_state(row)
        for row in rows
    ]
