"""Dashboard data aggregation for TitanAI.

This module is deliberately defensive: the dashboard should stay available even
when one optional database/table is missing or the trading scheduler is stopped.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = APP_DIR / "data"

SCHEDULER_HEALTH_FILE = DATA_DIR / "scheduler_health.json"
NOTIFICATION_STATE_FILE = DATA_DIR / "notification_state.json"

# The code checks common database names used by TitanAI versions.
STATE_DB_CANDIDATES = (
    DATA_DIR / "persistent_trade_state.db",
    DATA_DIR / "trade_state.db",
    DATA_DIR / "titanai_state.db",
)
JOURNAL_DB_CANDIDATES = (
    DATA_DIR / "trade_journal.db",
    DATA_DIR / "journal.db",
    DATA_DIR / "titanai_journal.db",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _find_existing(candidates: tuple[Path, ...]) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {str(row["name"]) for row in rows}


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {str(row["name"]) for row in rows}


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _pick_table(
    connection: sqlite3.Connection,
    preferred_names: tuple[str, ...],
) -> str | None:
    tables = _table_names(connection)
    for name in preferred_names:
        if name in tables:
            return name
    return None


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def get_scheduler_health() -> dict[str, Any]:
    payload = _read_json(
        SCHEDULER_HEALTH_FILE,
        {
            "status": "unknown",
            "running": False,
            "reason": "No scheduler health file has been written yet",
        },
    )

    last_success = payload.get("last_success_at")
    stale = None
    if last_success:
        try:
            parsed = datetime.fromisoformat(str(last_success).replace("Z", "+00:00"))
            stale = (_utc_now() - parsed).total_seconds() > 180
        except Exception:
            stale = None

    payload["stale"] = stale
    payload["health_file"] = str(SCHEDULER_HEALTH_FILE)
    return payload


def get_notification_health() -> dict[str, Any]:
    state = _read_json(NOTIFICATION_STATE_FILE, {})
    return {
        "configured": bool(state),
        "last_sent_at": state.get("last_sent_at"),
        "deduplicated_event_count": len(state.get("sent_event_keys", [])),
    }


def get_open_positions(limit: int = 50) -> list[dict[str, Any]]:
    database = _find_existing(STATE_DB_CANDIDATES)
    if database is None:
        return []

    try:
        with _connect(database) as connection:
            table = _pick_table(
                connection,
                (
                    "position_states",
                    "positions",
                    "persistent_position_states",
                    "trade_positions",
                ),
            )
            if table is None:
                return []

            columns = _columns(connection, table)
            order_column = next(
                (
                    name
                    for name in (
                        "updated_at",
                        "last_updated_at",
                        "created_at",
                        "id",
                    )
                    if name in columns
                ),
                None,
            )

            where_clause = ""
            parameters: list[Any] = []
            if "status" in columns:
                where_clause = (
                    "WHERE UPPER(COALESCE(status, '')) "
                    "IN ('OPEN', 'ACTIVE', 'PROTECTED')"
                )

            order_clause = (
                f'ORDER BY "{order_column}" DESC' if order_column else ""
            )
            rows = connection.execute(
                f'SELECT * FROM "{table}" {where_clause} '
                f'{order_clause} LIMIT ?',
                [*parameters, max(1, min(limit, 500))],
            ).fetchall()

            return [
                {
                    **_row_to_dict(row),
                    "_database": database.name,
                    "_table": table,
                }
                for row in rows
            ]
    except Exception:
        return []


def get_recent_cycles(limit: int = 50) -> list[dict[str, Any]]:
    database = _find_existing(JOURNAL_DB_CANDIDATES)
    if database is None:
        return []

    try:
        with _connect(database) as connection:
            table = _pick_table(
                connection,
                (
                    "trade_cycles",
                    "cycles",
                    "journal_cycles",
                    "trade_journal",
                ),
            )
            if table is None:
                return []

            columns = _columns(connection, table)
            order_column = next(
                (
                    name
                    for name in (
                        "completed_at",
                        "created_at",
                        "started_at",
                        "timestamp",
                        "id",
                    )
                    if name in columns
                ),
                None,
            )
            order_clause = (
                f'ORDER BY "{order_column}" DESC' if order_column else ""
            )
            rows = connection.execute(
                f'SELECT * FROM "{table}" {order_clause} LIMIT ?',
                (max(1, min(limit, 500)),),
            ).fetchall()

            return [
                {
                    **_row_to_dict(row),
                    "_database": database.name,
                    "_table": table,
                }
                for row in rows
            ]
    except Exception:
        return []


def _extract_pnl(row: dict[str, Any]) -> float:
    for key in (
        "realised_pnl",
        "realized_pnl",
        "pnl",
        "profit_loss",
        "net_pnl",
    ):
        if key in row and row[key] is not None:
            return _coerce_float(row[key])
    return 0.0


def _extract_result(row: dict[str, Any]) -> str:
    for key in ("result", "outcome", "trade_result", "status"):
        value = row.get(key)
        if value is not None:
            return str(value).strip().upper()
    pnl = _extract_pnl(row)
    if pnl > 0:
        return "WIN"
    if pnl < 0:
        return "LOSS"
    return "UNKNOWN"


def get_performance_summary() -> dict[str, Any]:
    cycles = get_recent_cycles(limit=500)
    wins = 0
    losses = 0
    realised_pnl = 0.0
    executed = 0
    skipped = 0

    for row in cycles:
        status = str(
            row.get("execution_status")
            or row.get("status")
            or ""
        ).lower()

        if status == "skipped":
            skipped += 1

        result = _extract_result(row)
        pnl = _extract_pnl(row)
        realised_pnl += pnl

        if result in {"WIN", "WON", "PROFIT", "TP", "TAKE_PROFIT"} or pnl > 0:
            wins += 1
            executed += 1
        elif result in {"LOSS", "LOST", "SL", "STOP_LOSS"} or pnl < 0:
            losses += 1
            executed += 1
        elif status in {"executed", "protected", "closed", "filled"}:
            executed += 1

    completed = wins + losses
    win_rate = (wins / completed * 100.0) if completed else 0.0

    return {
        "cycle_count": len(cycles),
        "executed_trades": executed,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 2),
        "realised_pnl": round(realised_pnl, 8),
        "skipped_cycles": skipped,
    }


def get_overview() -> dict[str, Any]:
    positions = get_open_positions()
    health = get_scheduler_health()
    performance = get_performance_summary()

    unrealised_pnl = 0.0
    protected_positions = 0
    for position in positions:
        unrealised_pnl += _coerce_float(
            position.get("unrealised_pnl")
            or position.get("unrealized_pnl")
        )
        if bool(position.get("protection_verified")):
            protected_positions += 1

    return {
        "generated_at": _utc_now().isoformat(timespec="seconds"),
        "scheduler": health,
        "telegram": get_notification_health(),
        "performance": performance,
        "positions": {
            "open_count": len(positions),
            "protected_count": protected_positions,
            "unrealised_pnl": round(unrealised_pnl, 8),
        },
    }