"""TitanAI persistence backend selection and synchronous PostgreSQL pooling."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg
from dotenv import load_dotenv
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


load_dotenv(dotenv_path=".env")


_POOL: ConnectionPool | None = None
_POOL_LOCK = threading.Lock()


def get_persistence_backend() -> str:
    backend = str(
        os.getenv(
            "TITANAI_DATABASE_BACKEND",
            "sqlite",
        )
    ).strip().lower()

    if backend not in {"sqlite", "postgres"}:
        raise RuntimeError(
            "TITANAI_DATABASE_BACKEND must be "
            "'sqlite' or 'postgres'"
        )

    return backend


def using_postgres() -> bool:
    return get_persistence_backend() == "postgres"


def _postgres_url() -> str:
    raw = str(
        os.getenv("DATABASE_URL", "")
    ).strip()

    if not raw:
        raise RuntimeError(
            "DATABASE_URL is required when "
            "TITANAI_DATABASE_BACKEND=postgres"
        )

    if raw.startswith("postgresql+asyncpg://"):
        raw = (
            "postgresql://"
            + raw[len("postgresql+asyncpg://"):]
        )

    parts = urlsplit(raw)

    query = dict(
        parse_qsl(
            parts.query,
            keep_blank_values=True,
        )
    )

    # Avoid client compatibility differences.
    query.pop("channel_binding", None)

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def _create_pool() -> ConnectionPool:
    return ConnectionPool(
        conninfo=_postgres_url(),
        min_size=0,
        max_size=4,
        open=False,
        timeout=60.0,
        max_waiting=20,
        max_lifetime=1800.0,
        max_idle=300.0,
        kwargs={
            "row_factory": dict_row,
            "connect_timeout": 15,
        },
        name="titanai-persistence",
    )


def get_postgres_pool() -> ConnectionPool:
    global _POOL

    if not using_postgres():
        raise RuntimeError(
            "PostgreSQL pool requested while "
            "TITANAI_DATABASE_BACKEND is not postgres"
        )

    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                pool = _create_pool()
                pool.open(wait=False)
                _POOL = pool

    return _POOL


def close_postgres_pool() -> None:
    global _POOL

    with _POOL_LOCK:
        pool = _POOL
        _POOL = None

    if pool is not None:
        pool.close()


@contextmanager
def postgres_connection() -> Iterator[Connection]:
    pool = get_postgres_pool()

    with pool.connection(
        timeout=60.0
    ) as connection:
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def postgres_fetchone(
    query: str,
    parameters: tuple | list = (),
) -> dict | None:
    with postgres_connection() as connection:
        row = connection.execute(
            query,
            parameters,
        ).fetchone()

    return dict(row) if row else None


def postgres_fetchall(
    query: str,
    parameters: tuple | list = (),
) -> list[dict]:
    with postgres_connection() as connection:
        rows = connection.execute(
            query,
            parameters,
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def postgres_execute(
    query: str,
    parameters: tuple | list = (),
) -> int:
    with postgres_connection() as connection:
        cursor = connection.execute(
            query,
            parameters,
        )
        return int(cursor.rowcount or 0)


def backend_diagnostics() -> dict:
    backend = get_persistence_backend()

    result = {
        "backend": backend,
        "database_url_configured": bool(
            str(
                os.getenv(
                    "DATABASE_URL",
                    "",
                )
            ).strip()
        ),
    }

    if backend != "postgres":
        result["connection_tested"] = False
        return result

    with postgres_connection() as connection:
        row = connection.execute(
            """
            SELECT
                current_database() AS database,
                current_user AS database_user,
                version() AS postgres_version
            """
        ).fetchone()

    result.update(
        {
            "connection_tested": True,
            "database": row["database"],
            "database_user": row["database_user"],
            "postgres_version": row[
                "postgres_version"
            ],
        }
    )

    return result
