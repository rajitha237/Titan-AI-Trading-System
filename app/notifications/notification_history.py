"""SQLite Notification History v32."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "titanai_notifications.db"
)

_LOCK = threading.RLock()


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
def _connection() -> Iterator[
    sqlite3.Connection
]:
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
        CREATE TABLE IF NOT EXISTS notification_history (
            notification_id INTEGER
                PRIMARY KEY AUTOINCREMENT,
            event_key TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            cycle_id TEXT,
            symbol TEXT,
            delivery_status TEXT NOT NULL,
            telegram_status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS
        idx_notification_history_created
        ON notification_history(
            notification_id DESC
        );
        """
    )


def save_notification(
    notification: dict,
    *,
    delivery_status: str,
    telegram_status: str,
) -> dict:
    event_key = str(
        notification.get(
            "event_key",
            "",
        )
    )

    if not event_key:
        raise ValueError(
            "Notification event_key is required"
        )

    with _connection() as connection:
        connection.execute(
            """
            INSERT INTO notification_history(
                event_key,
                event_type,
                severity,
                title,
                message,
                cycle_id,
                symbol,
                delivery_status,
                telegram_status,
                payload_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_key) DO UPDATE SET
                delivery_status =
                    excluded.delivery_status,
                telegram_status =
                    excluded.telegram_status,
                payload_json =
                    excluded.payload_json
            """,
            (
                event_key,
                notification.get(
                    "event_type"
                ),
                notification.get(
                    "severity"
                ),
                notification.get("title"),
                notification.get("message"),
                notification.get(
                    "cycle_id"
                ),
                notification.get("symbol"),
                str(delivery_status),
                str(telegram_status),
                _json(notification),
                notification.get(
                    "created_at"
                ),
            ),
        )

        row = connection.execute(
            """
            SELECT *
            FROM notification_history
            WHERE event_key = ?
            """,
            (event_key,),
        ).fetchone()

    return _row_to_dict(row)


def _row_to_dict(
    row: sqlite3.Row,
) -> dict:
    return {
        "notification_id": (
            row["notification_id"]
        ),
        "event_key": row["event_key"],
        "event_type": row["event_type"],
        "severity": row["severity"],
        "title": row["title"],
        "message": row["message"],
        "cycle_id": row["cycle_id"],
        "symbol": row["symbol"],
        "delivery_status": (
            row["delivery_status"]
        ),
        "telegram_status": (
            row["telegram_status"]
        ),
        "payload": _loads(
            row["payload_json"],
            {},
        ),
        "created_at": row["created_at"],
    }


def list_notifications(
    *,
    limit: int = 50,
    severity: str | None = None,
) -> list[dict]:
    limit = max(
        1,
        min(500, int(limit)),
    )

    query = (
        "SELECT * "
        "FROM notification_history"
    )
    params: list[Any] = []

    if severity:
        query += " WHERE severity = ?"
        params.append(
            str(severity).upper()
        )

    query += (
        " ORDER BY notification_id DESC "
        "LIMIT ?"
    )
    params.append(limit)

    with _connection() as connection:
        rows = connection.execute(
            query,
            params,
        ).fetchall()

    return [
        _row_to_dict(row)
        for row in rows
    ]


def count_notifications() -> int:
    with _connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM notification_history
            """
        ).fetchone()

    return int(row["count"])


# ---------------------------------------------------------------------------
# PostgreSQL backend compatibility layer
# ---------------------------------------------------------------------------

from app.db.persistence_backend import (
    postgres_connection,
    using_postgres,
)


_sqlite_save_notification = save_notification
_sqlite_list_notifications = list_notifications
_sqlite_count_notifications = count_notifications


def save_notification(
    notification: dict,
    *,
    delivery_status: str,
    telegram_status: str,
) -> dict:
    if not using_postgres():
        return _sqlite_save_notification(
            notification,
            delivery_status=delivery_status,
            telegram_status=telegram_status,
        )

    event_key = str(
        notification.get("event_key", "")
    )

    if not event_key:
        raise ValueError(
            "Notification event_key is required"
        )

    with postgres_connection() as connection:
        row = connection.execute(
            """
            INSERT INTO notification_history(
                event_key,
                event_type,
                severity,
                title,
                message,
                cycle_id,
                symbol,
                delivery_status,
                telegram_status,
                payload_json,
                created_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT(event_key) DO UPDATE SET
                delivery_status =
                    EXCLUDED.delivery_status,
                telegram_status =
                    EXCLUDED.telegram_status,
                payload_json =
                    EXCLUDED.payload_json
            RETURNING *
            """,
            (
                event_key,
                notification.get("event_type"),
                notification.get("severity"),
                notification.get("title"),
                notification.get("message"),
                notification.get("cycle_id"),
                notification.get("symbol"),
                str(delivery_status),
                str(telegram_status),
                _json(notification),
                notification.get("created_at"),
            ),
        ).fetchone()

    return _row_to_dict(row)


def list_notifications(
    *,
    limit: int = 50,
    severity: str | None = None,
) -> list[dict]:
    if not using_postgres():
        return _sqlite_list_notifications(
            limit=limit,
            severity=severity,
        )

    limit = max(
        1,
        min(500, int(limit)),
    )

    parameters: list[Any] = []

    query = """
        SELECT *
        FROM notification_history
    """

    if severity:
        query += " WHERE severity = %s"
        parameters.append(
            str(severity).upper()
        )

    query += """
        ORDER BY notification_id DESC
        LIMIT %s
    """
    parameters.append(limit)

    with postgres_connection() as connection:
        rows = connection.execute(
            query,
            parameters,
        ).fetchall()

    return [
        _row_to_dict(row)
        for row in rows
    ]


def count_notifications() -> int:
    if not using_postgres():
        return _sqlite_count_notifications()

    with postgres_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM notification_history
            """
        ).fetchone()

    return int(row["count"])
