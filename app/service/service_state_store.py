"""TitanAI Persistent Service State Store v30."""

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
    / "titanai_service_state.db"
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
        CREATE TABLE IF NOT EXISTS service_state (
            state_key TEXT PRIMARY KEY,
            state_value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS service_heartbeats (
            heartbeat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            status TEXT NOT NULL,
            mode TEXT,
            cycle_id TEXT,
            payload TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS
        idx_service_heartbeats_created_at
        ON service_heartbeats(created_at DESC);
        """
    )


def set_state(
    state_key: str,
    state_value: Any,
) -> None:
    key = str(state_key or "").strip()

    if not key:
        raise ValueError(
            "state_key is required"
        )

    now = _utc_now()

    with _connection() as connection:
        connection.execute(
            """
            INSERT INTO service_state(
                state_key,
                state_value,
                updated_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(state_key) DO UPDATE SET
                state_value = excluded.state_value,
                updated_at = excluded.updated_at
            """,
            (
                key,
                _json(state_value),
                now,
            ),
        )


def get_state(
    state_key: str,
    default: Any = None,
) -> Any:
    with _connection() as connection:
        row = connection.execute(
            """
            SELECT state_value
            FROM service_state
            WHERE state_key = ?
            """,
            (
                str(state_key or "").strip(),
            ),
        ).fetchone()

    if not row:
        return default

    return _loads(
        row["state_value"],
        default,
    )


def delete_state(
    state_key: str,
) -> None:
    with _connection() as connection:
        connection.execute(
            """
            DELETE FROM service_state
            WHERE state_key = ?
            """,
            (
                str(state_key or "").strip(),
            ),
        )


def record_heartbeat(
    *,
    service_name: str,
    status: str,
    mode: str | None,
    cycle_id: str | None,
    payload: dict | None = None,
) -> int:
    now = _utc_now()

    with _connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO service_heartbeats(
                service_name,
                status,
                mode,
                cycle_id,
                payload,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(service_name),
                str(status),
                (
                    str(mode)
                    if mode is not None
                    else None
                ),
                (
                    str(cycle_id)
                    if cycle_id is not None
                    else None
                ),
                _json(payload or {}),
                now,
            ),
        )

        return int(cursor.lastrowid)


def get_latest_heartbeat(
    service_name: str,
) -> dict | None:
    with _connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM service_heartbeats
            WHERE service_name = ?
            ORDER BY heartbeat_id DESC
            LIMIT 1
            """,
            (
                str(service_name),
            ),
        ).fetchone()

    if not row:
        return None

    return {
        "heartbeat_id": row["heartbeat_id"],
        "service_name": row["service_name"],
        "status": row["status"],
        "mode": row["mode"],
        "cycle_id": row["cycle_id"],
        "payload": _loads(
            row["payload"],
            {},
        ),
        "created_at": row["created_at"],
    }


# ---------------------------------------------------------------------------
# PostgreSQL backend compatibility layer
# ---------------------------------------------------------------------------

from app.db.persistence_backend import (
    postgres_connection,
    using_postgres,
)


_sqlite_set_state = set_state
_sqlite_get_state = get_state
_sqlite_delete_state = delete_state
_sqlite_record_heartbeat = record_heartbeat
_sqlite_get_latest_heartbeat = get_latest_heartbeat


def set_state(
    state_key: str,
    state_value: Any,
) -> None:
    if not using_postgres():
        return _sqlite_set_state(
            state_key,
            state_value,
        )

    key = str(state_key or "").strip()
    if not key:
        raise ValueError("state_key is required")

    with postgres_connection() as connection:
        connection.execute(
            """
            INSERT INTO service_state(
                state_key,
                state_value,
                updated_at
            )
            VALUES (%s, %s, %s)
            ON CONFLICT(state_key) DO UPDATE SET
                state_value = EXCLUDED.state_value,
                updated_at = EXCLUDED.updated_at
            """,
            (
                key,
                _json(state_value),
                _utc_now(),
            ),
        )


def get_state(
    state_key: str,
    default: Any = None,
) -> Any:
    if not using_postgres():
        return _sqlite_get_state(
            state_key,
            default,
        )

    with postgres_connection() as connection:
        row = connection.execute(
            """
            SELECT state_value
            FROM service_state
            WHERE state_key = %s
            """,
            (
                str(state_key or "").strip(),
            ),
        ).fetchone()

    if not row:
        return default

    return _loads(
        row["state_value"],
        default,
    )


def delete_state(
    state_key: str,
) -> None:
    if not using_postgres():
        return _sqlite_delete_state(state_key)

    with postgres_connection() as connection:
        connection.execute(
            """
            DELETE FROM service_state
            WHERE state_key = %s
            """,
            (
                str(state_key or "").strip(),
            ),
        )


def record_heartbeat(
    *,
    service_name: str,
    status: str,
    mode: str | None,
    cycle_id: str | None,
    payload: dict | None = None,
) -> int:
    if not using_postgres():
        return _sqlite_record_heartbeat(
            service_name=service_name,
            status=status,
            mode=mode,
            cycle_id=cycle_id,
            payload=payload,
        )

    with postgres_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO service_heartbeats(
                service_name,
                status,
                mode,
                cycle_id,
                payload,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING heartbeat_id
            """,
            (
                str(service_name),
                str(status),
                (
                    str(mode)
                    if mode is not None
                    else None
                ),
                (
                    str(cycle_id)
                    if cycle_id is not None
                    else None
                ),
                _json(payload or {}),
                _utc_now(),
            ),
        ).fetchone()

    return int(row["heartbeat_id"])


def get_latest_heartbeat(
    service_name: str,
) -> dict | None:
    if not using_postgres():
        return _sqlite_get_latest_heartbeat(
            service_name
        )

    with postgres_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM service_heartbeats
            WHERE service_name = %s
            ORDER BY heartbeat_id DESC
            LIMIT 1
            """,
            (str(service_name),),
        ).fetchone()

    if not row:
        return None

    return {
        "heartbeat_id": row["heartbeat_id"],
        "service_name": row["service_name"],
        "status": row["status"],
        "mode": row["mode"],
        "cycle_id": row["cycle_id"],
        "payload": _loads(
            row["payload"],
            {},
        ),
        "created_at": row["created_at"],
    }
