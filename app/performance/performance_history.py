"""SQLite Performance History v34."""

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
    / "titanai_performance.db"
)

_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(timespec="milliseconds")


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
        connection.row_factory = (
            sqlite3.Row
        )

        try:
            connection.execute(
                "PRAGMA journal_mode=WAL"
            )
            connection.execute(
                "PRAGMA busy_timeout=15000"
            )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                performance_snapshots (
                    snapshot_id INTEGER
                        PRIMARY KEY AUTOINCREMENT,
                    snapshot_key TEXT NOT NULL
                        UNIQUE,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
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


def save_performance_snapshot(
    *,
    snapshot_key: str,
    payload: dict,
) -> dict:
    key = str(
        snapshot_key or ""
    ).strip()

    if not key:
        raise ValueError(
            "snapshot_key is required"
        )

    created_at = _utc_now()

    with _connection() as connection:
        connection.execute(
            """
            INSERT INTO performance_snapshots(
                snapshot_key,
                payload_json,
                created_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(snapshot_key)
            DO UPDATE SET
                payload_json =
                    excluded.payload_json,
                created_at =
                    excluded.created_at
            """,
            (
                key,
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    default=str,
                ),
                created_at,
            ),
        )

        row = connection.execute(
            """
            SELECT *
            FROM performance_snapshots
            WHERE snapshot_key = ?
            """,
            (key,),
        ).fetchone()

    return {
        "snapshot_id": (
            row["snapshot_id"]
        ),
        "snapshot_key": (
            row["snapshot_key"]
        ),
        "payload": json.loads(
            row["payload_json"]
        ),
        "created_at": (
            row["created_at"]
        ),
    }


def list_performance_snapshots(
    *,
    limit: int = 50,
) -> list[dict]:
    limit = max(
        1,
        min(500, int(limit)),
    )

    with _connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM performance_snapshots
            ORDER BY snapshot_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "snapshot_id": (
                row["snapshot_id"]
            ),
            "snapshot_key": (
                row["snapshot_key"]
            ),
            "payload": json.loads(
                row["payload_json"]
            ),
            "created_at": (
                row["created_at"]
            ),
        }
        for row in rows
    ]
