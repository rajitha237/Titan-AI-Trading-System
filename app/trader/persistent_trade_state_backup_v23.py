"""TitanAI persistent trade state store.

SQLite-backed state for open positions and position-management milestones.
The module uses only Python's standard library and is safe to call on every
runner cycle. Writes are transactional and the database survives restarts.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "titanai_state.db"
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
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
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=15000")
            _initialise(connection)
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _initialise(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS position_state (
            position_key TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            original_quantity REAL NOT NULL,
            current_quantity REAL NOT NULL,
            mark_price REAL NOT NULL DEFAULT 0,
            break_even_moved INTEGER NOT NULL DEFAULT 0,
            trailing_activated INTEGER NOT NULL DEFAULT 0,
            trailing_stop_price REAL NOT NULL DEFAULT 0,
            completed_partial_stages TEXT NOT NULL DEFAULT '[]',
            protection_verified INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'OPEN',
            opened_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            closed_at TEXT,
            metadata TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_position_state_symbol_status
        ON position_state(symbol, status);

        CREATE TABLE IF NOT EXISTS state_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time TEXT NOT NULL,
            symbol TEXT,
            event_type TEXT NOT NULL,
            position_key TEXT,
            payload TEXT NOT NULL DEFAULT '{}'
        );
        """
    )


def _position_key(symbol: str, side: str, entry_price: float) -> str:
    return f"{symbol.upper()}:{side.upper()}:{entry_price:.12g}"


def _position_values(position: dict) -> tuple[str, str, float, float, float]:
    symbol = str(position.get("symbol", "")).upper()
    amount = _safe_float(
        position.get("positionAmt", position.get("position_amount", 0.0))
    )
    side = "BUY" if amount > 0 else "SELL" if amount < 0 else "NONE"
    entry = _safe_float(position.get("entryPrice", position.get("entry_price", 0.0)))
    mark = _safe_float(position.get("markPrice", position.get("mark_price", 0.0)))
    return symbol, side, entry, abs(amount), mark


def record_event(
    event_type: str,
    payload: dict | None = None,
    *,
    symbol: str | None = None,
    position_key: str | None = None,
) -> int:
    with _connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO state_events(event_time, symbol, event_type, position_key, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (_utc_now(), symbol, event_type, position_key, _json(payload or {})),
        )
        return int(cursor.lastrowid)


def upsert_open_position(position: dict, metadata: dict | None = None) -> dict:
    symbol, side, entry, quantity, mark = _position_values(position)
    if not symbol or side == "NONE" or entry <= 0 or quantity <= 0:
        raise ValueError("A valid non-zero open position is required")

    key = _position_key(symbol, side, entry)
    now = _utc_now()

    with _connection() as connection:
        existing = connection.execute(
            "SELECT original_quantity, opened_at, metadata FROM position_state WHERE position_key = ?",
            (key,),
        ).fetchone()

        original_quantity = max(
            quantity,
            _safe_float(existing["original_quantity"], quantity) if existing else quantity,
        )
        opened_at = existing["opened_at"] if existing else now
        merged_metadata = _loads(existing["metadata"], {}) if existing else {}
        merged_metadata.update(metadata or {})

        connection.execute(
            """
            INSERT INTO position_state(
                position_key, symbol, side, entry_price, original_quantity,
                current_quantity, mark_price, status, opened_at, updated_at,
                closed_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, NULL, ?)
            ON CONFLICT(position_key) DO UPDATE SET
                original_quantity = excluded.original_quantity,
                current_quantity = excluded.current_quantity,
                mark_price = excluded.mark_price,
                status = 'OPEN',
                updated_at = excluded.updated_at,
                closed_at = NULL,
                metadata = excluded.metadata
            """,
            (
                key, symbol, side, entry, original_quantity, quantity, mark,
                opened_at, now, _json(merged_metadata),
            ),
        )

    return get_position_state(symbol=symbol, side=side, entry_price=entry) or {}


def update_position_management(
    *,
    symbol: str,
    side: str,
    entry_price: float,
    current_quantity: float | None = None,
    mark_price: float | None = None,
    break_even_moved: bool | None = None,
    trailing_activated: bool | None = None,
    trailing_stop_price: float | None = None,
    completed_partial_stages: list[str] | None = None,
    protection_verified: bool | None = None,
    metadata: dict | None = None,
) -> dict:
    key = _position_key(symbol, side, entry_price)
    current = get_position_state(symbol=symbol, side=side, entry_price=entry_price)
    if current is None:
        raise KeyError(f"Position state does not exist: {key}")

    values = {
        "current_quantity": current["current_quantity"] if current_quantity is None else abs(_safe_float(current_quantity)),
        "mark_price": current["mark_price"] if mark_price is None else _safe_float(mark_price),
        "break_even_moved": current["break_even_moved"] if break_even_moved is None else bool(break_even_moved),
        "trailing_activated": current["trailing_activated"] if trailing_activated is None else bool(trailing_activated),
        "trailing_stop_price": current["trailing_stop_price"] if trailing_stop_price is None else _safe_float(trailing_stop_price),
        "completed_partial_stages": current["completed_partial_stages"] if completed_partial_stages is None else list(dict.fromkeys(completed_partial_stages)),
        "protection_verified": current["protection_verified"] if protection_verified is None else bool(protection_verified),
        "metadata": {**current["metadata"], **(metadata or {})},
    }

    with _connection() as connection:
        connection.execute(
            """
            UPDATE position_state SET
                current_quantity = ?, mark_price = ?, break_even_moved = ?,
                trailing_activated = ?, trailing_stop_price = ?,
                completed_partial_stages = ?, protection_verified = ?,
                metadata = ?, updated_at = ?
            WHERE position_key = ?
            """,
            (
                values["current_quantity"], values["mark_price"],
                int(values["break_even_moved"]), int(values["trailing_activated"]),
                values["trailing_stop_price"], _json(values["completed_partial_stages"]),
                int(values["protection_verified"]), _json(values["metadata"]),
                _utc_now(), key,
            ),
        )

    return get_position_state(symbol=symbol, side=side, entry_price=entry_price) or {}


def close_position_state(
    *,
    symbol: str,
    side: str | None = None,
    entry_price: float | None = None,
    metadata: dict | None = None,
) -> int:
    clauses = ["symbol = ?", "status = 'OPEN'"]
    params: list[Any] = [symbol.upper()]
    if side:
        clauses.append("side = ?")
        params.append(side.upper())
    if entry_price is not None:
        clauses.append("ABS(entry_price - ?) < 0.00000001")
        params.append(_safe_float(entry_price))

    rows = []
    with _connection() as connection:
        rows = connection.execute(
            f"SELECT position_key, metadata FROM position_state WHERE {' AND '.join(clauses)}",
            params,
        ).fetchall()
        now = _utc_now()
        for row in rows:
            merged = _loads(row["metadata"], {})
            merged.update(metadata or {})
            connection.execute(
                """
                UPDATE position_state SET status='CLOSED', current_quantity=0,
                    closed_at=?, updated_at=?, metadata=? WHERE position_key=?
                """,
                (now, now, _json(merged), row["position_key"]),
            )
    return len(rows)


def get_position_state(
    *, symbol: str, side: str | None = None, entry_price: float | None = None
) -> dict | None:
    clauses = ["symbol = ?"]
    params: list[Any] = [symbol.upper()]
    if side:
        clauses.append("side = ?")
        params.append(side.upper())
    if entry_price is not None:
        clauses.append("ABS(entry_price - ?) < 0.00000001")
        params.append(_safe_float(entry_price))

    with _connection() as connection:
        row = connection.execute(
            f"SELECT * FROM position_state WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT 1",
            params,
        ).fetchone()
    return _row_to_state(row) if row else None


def list_position_states(status: str | None = None) -> list[dict]:
    query = "SELECT * FROM position_state"
    params: list[Any] = []
    if status:
        query += " WHERE status = ?"
        params.append(status.upper())
    query += " ORDER BY updated_at DESC"
    with _connection() as connection:
        rows = connection.execute(query, params).fetchall()
    return [_row_to_state(row) for row in rows]


def _row_to_state(row: sqlite3.Row) -> dict:
    return {
        "position_key": row["position_key"],
        "symbol": row["symbol"],
        "side": row["side"],
        "entry_price": row["entry_price"],
        "original_quantity": row["original_quantity"],
        "current_quantity": row["current_quantity"],
        "mark_price": row["mark_price"],
        "break_even_moved": bool(row["break_even_moved"]),
        "trailing_activated": bool(row["trailing_activated"]),
        "trailing_stop_price": row["trailing_stop_price"],
        "completed_partial_stages": _loads(row["completed_partial_stages"], []),
        "protection_verified": bool(row["protection_verified"]),
        "status": row["status"],
        "opened_at": row["opened_at"],
        "updated_at": row["updated_at"],
        "closed_at": row["closed_at"],
        "metadata": _loads(row["metadata"], {}),
    }


def sync_cycle_state(
    *,
    open_positions: list[dict],
    partial_take_profit_results: list[dict] | None = None,
    break_even_results: list[dict] | None = None,
    trailing_stop_results: list[dict] | None = None,
    protection_results: list[dict] | None = None,
) -> dict:
    """Synchronise exchange positions and manager milestones into SQLite."""
    active_symbols: set[str] = set()
    synced: list[dict] = []
    errors: list[str] = []

    for position in open_positions or []:
        try:
            state = upsert_open_position(position)
            active_symbols.add(state["symbol"])
            synced.append(state)
        except Exception as error:
            errors.append(str(error))

    for result_list, manager_name in (
        (partial_take_profit_results or [], "partial_take_profit"),
        (break_even_results or [], "break_even"),
        (trailing_stop_results or [], "trailing_stop"),
    ):
        for item in result_list:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).upper()
            side = str(item.get("position_side", "")).upper()
            entry = _safe_float(item.get("entry_price"))
            if not symbol or side not in {"BUY", "SELL"} or entry <= 0:
                continue
            try:
                current = get_position_state(symbol=symbol, side=side, entry_price=entry)
                if current is None:
                    continue
                changes: dict[str, Any] = {
                    "mark_price": item.get("mark_price"),
                    "metadata": {f"last_{manager_name}_result": item},
                }
                if manager_name == "partial_take_profit":
                    changes["current_quantity"] = item.get("current_quantity", item.get("remaining_quantity"))
                    changes["completed_partial_stages"] = item.get("completed_stages", current["completed_partial_stages"])
                    changes["protection_verified"] = bool(
                        item.get("protected", item.get("protection", {}).get("protected", current["protection_verified"]))
                    )
                elif manager_name == "break_even":
                    changes["break_even_moved"] = bool(item.get("moved", False)) or current["break_even_moved"]
                elif manager_name == "trailing_stop":
                    changes["trailing_activated"] = (
                        bool(item.get("moved", False))
                        or str(item.get("status", "")).lower() in {"activated", "moved", "updated"}
                        or current["trailing_activated"]
                    )
                    changes["trailing_stop_price"] = item.get(
                        "new_stop_price", item.get("trailing_stop_price", current["trailing_stop_price"])
                    )
                update_position_management(symbol=symbol, side=side, entry_price=entry, **changes)
            except Exception as error:
                errors.append(f"{symbol} {manager_name}: {error}")

    # Synchronise read-only exchange protection inspections.
    for item in protection_results or []:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "")).upper()
        side = str(item.get("position_side", "")).upper()
        entry = _safe_float(item.get("entry_price"))
        if not symbol:
            continue
        try:
            current = get_position_state(
                symbol=symbol,
                side=side if side in {"BUY", "SELL"} else None,
                entry_price=entry if entry > 0 else None,
            )
            if current is None:
                continue
            update_position_management(
                symbol=current["symbol"],
                side=current["side"],
                entry_price=current["entry_price"],
                protection_verified=bool(item.get("protected", False)),
                metadata={"last_protection_verification": item},
            )
        except Exception as error:
            errors.append(f"{symbol} protection: {error}")

    # Mark database positions closed when their symbol is no longer active.
    for state in list_position_states(status="OPEN"):
        if state["symbol"] not in active_symbols:
            close_position_state(symbol=state["symbol"], side=state["side"], entry_price=state["entry_price"], metadata={"closed_by": "exchange_sync"})

    return {
        "status": "success" if not errors else "partial",
        "database": str(DB_PATH),
        "active_positions": len(active_symbols),
        "synced_positions": len(synced),
        "errors": errors,
    }