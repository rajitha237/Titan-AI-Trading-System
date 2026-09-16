from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "app" / "data"


@dataclass(frozen=True)
class TableConfig:
    sqlite_file: str
    table: str
    conflict_columns: tuple[str, ...]
    boolean_columns: tuple[str, ...] = ()
    sequence_column: str | None = None


TABLES: tuple[TableConfig, ...] = (
    TableConfig(
        sqlite_file="titanai_experience.db",
        table="experiences",
        conflict_columns=("id",),
        sequence_column="id",
    ),
    TableConfig(
        sqlite_file="titanai_journal.db",
        table="cycles",
        conflict_columns=("id",),
        boolean_columns=("execute_requested",),
        sequence_column="id",
    ),
    TableConfig(
        sqlite_file="titanai_journal.db",
        table="trade_events",
        conflict_columns=("id",),
        sequence_column="id",
    ),
    TableConfig(
        sqlite_file="titanai_notifications.db",
        table="notification_history",
        conflict_columns=("notification_id",),
        sequence_column="notification_id",
    ),
    TableConfig(
        sqlite_file="titanai_order_recovery.db",
        table="order_recovery_state",
        conflict_columns=("order_key",),
        boolean_columns=(
            "reduce_only",
            "is_algo_order",
        ),
    ),
    TableConfig(
        sqlite_file="titanai_performance.db",
        table="performance_snapshots",
        conflict_columns=("snapshot_id",),
        sequence_column="snapshot_id",
    ),
    TableConfig(
        sqlite_file="titanai_service_state.db",
        table="service_state",
        conflict_columns=("state_key",),
    ),
    TableConfig(
        sqlite_file="titanai_service_state.db",
        table="service_heartbeats",
        conflict_columns=("heartbeat_id",),
        sequence_column="heartbeat_id",
    ),
    TableConfig(
        sqlite_file="titanai_state.db",
        table="completed_trades",
        conflict_columns=("trade_id",),
    ),
    TableConfig(
        sqlite_file="titanai_state.db",
        table="position_state",
        conflict_columns=("position_key",),
        boolean_columns=(
            "break_even_moved",
            "trailing_activated",
            "protection_verified",
        ),
    ),
    TableConfig(
        sqlite_file="titanai_state.db",
        table="state_events",
        conflict_columns=("id",),
        sequence_column="id",
    ),
    TableConfig(
        sqlite_file="titanai_state.db",
        table="system_locks",
        conflict_columns=("lock_name",),
        boolean_columns=("locked",),
    ),
)


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def read_sqlite_rows(
    database_path: Path,
    table: str,
) -> tuple[list[str], list[tuple[Any, ...]]]:
    if not database_path.exists():
        raise FileNotFoundError(
            f"SQLite database not found: {database_path}"
        )

    connection = sqlite3.connect(
        f"file:{database_path}?mode=ro",
        uri=True,
        timeout=15.0,
    )

    try:
        connection.row_factory = sqlite3.Row

        exists = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            """,
            (table,),
        ).fetchone()

        if not exists:
            raise RuntimeError(
                f"Table {table!r} not found in {database_path}"
            )

        rows = connection.execute(
            f"SELECT * FROM {quote_identifier(table)}"
        ).fetchall()

        if rows:
            columns = list(rows[0].keys())
            values = [
                tuple(row[column] for column in columns)
                for row in rows
            ]
        else:
            info = connection.execute(
                f"PRAGMA table_info({quote_identifier(table)})"
            ).fetchall()
            columns = [
                str(row["name"])
                for row in info
            ]
            values = []

        return columns, values

    finally:
        connection.close()


def convert_row(
    columns: list[str],
    row: tuple[Any, ...],
    boolean_columns: tuple[str, ...],
) -> tuple[Any, ...]:
    bool_columns = set(boolean_columns)

    converted: list[Any] = []

    for column, value in zip(columns, row):
        if column in bool_columns and value is not None:
            converted.append(bool(value))
        else:
            converted.append(value)

    return tuple(converted)


async def get_postgres_columns(
    connection: asyncpg.Connection,
    table: str,
) -> list[str]:
    rows = await connection.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = $1
        ORDER BY ordinal_position
        """,
        table,
    )

    return [
        str(row["column_name"])
        for row in rows
    ]


async def postgres_count(
    connection: asyncpg.Connection,
    table: str,
) -> int:
    value = await connection.fetchval(
        f"SELECT COUNT(*) FROM {quote_identifier(table)}"
    )
    return int(value)


async def migrate_table(
    connection: asyncpg.Connection,
    config: TableConfig,
) -> tuple[int, int]:
    database_path = DATA_DIR / config.sqlite_file

    columns, rows = read_sqlite_rows(
        database_path,
        config.table,
    )

    postgres_columns = await get_postgres_columns(
        connection,
        config.table,
    )

    if not postgres_columns:
        raise RuntimeError(
            f"PostgreSQL table not found: {config.table}"
        )

    if set(columns) != set(postgres_columns):
        missing_in_postgres = sorted(
            set(columns) - set(postgres_columns)
        )
        missing_in_sqlite = sorted(
            set(postgres_columns) - set(columns)
        )

        raise RuntimeError(
            f"SCHEMA_MISMATCH table={config.table} "
            f"missing_in_postgres={missing_in_postgres} "
            f"missing_in_sqlite={missing_in_sqlite}"
        )

    source_count = len(rows)

    if source_count == 0:
        target_count = await postgres_count(
            connection,
            config.table,
        )
        print(
            f"{config.table}: "
            f"SOURCE={source_count} TARGET={target_count}"
        )
        return source_count, target_count

    quoted_columns = ", ".join(
        quote_identifier(column)
        for column in columns
    )

    placeholders = ", ".join(
        f"${index}"
        for index in range(1, len(columns) + 1)
    )

    conflict_columns = ", ".join(
        quote_identifier(column)
        for column in config.conflict_columns
    )

    update_columns = [
        column
        for column in columns
        if column not in config.conflict_columns
    ]

    if update_columns:
        update_clause = ", ".join(
            (
                f"{quote_identifier(column)} = "
                f"EXCLUDED.{quote_identifier(column)}"
            )
            for column in update_columns
        )

        conflict_action = (
            f"DO UPDATE SET {update_clause}"
        )
    else:
        conflict_action = "DO NOTHING"

    sql = (
        f"INSERT INTO {quote_identifier(config.table)} "
        f"({quoted_columns}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_columns}) "
        f"{conflict_action}"
    )

    converted_rows = [
        convert_row(
            columns,
            row,
            config.boolean_columns,
        )
        for row in rows
    ]

    await connection.executemany(
        sql,
        converted_rows,
    )

    target_count = await postgres_count(
        connection,
        config.table,
    )

    print(
        f"{config.table}: "
        f"SOURCE={source_count} TARGET={target_count}"
    )

    return source_count, target_count


async def sync_sequence(
    connection: asyncpg.Connection,
    table: str,
    column: str,
) -> None:
    sequence_name = await connection.fetchval(
        """
        SELECT pg_get_serial_sequence($1, $2)
        """,
        f"public.{table}",
        column,
    )

    if not sequence_name:
        print(
            f"{table}: SEQUENCE=NOT_REQUIRED"
        )
        return

    max_value = await connection.fetchval(
        (
            f"SELECT MAX({quote_identifier(column)}) "
            f"FROM {quote_identifier(table)}"
        )
    )

    if max_value is None:
        await connection.execute(
            "SELECT setval($1::regclass, 1, false)",
            sequence_name,
        )
        next_value = 1
    else:
        await connection.execute(
            "SELECT setval($1::regclass, $2, true)",
            sequence_name,
            int(max_value),
        )
        next_value = int(max_value) + 1

    print(
        f"{table}: SEQUENCE_NEXT={next_value}"
    )


async def verify_all(
    connection: asyncpg.Connection,
) -> bool:
    print()
    print("=" * 72)
    print("FINAL ROW COUNT VERIFICATION")
    print("=" * 72)

    all_match = True

    for config in TABLES:
        database_path = DATA_DIR / config.sqlite_file

        _, rows = read_sqlite_rows(
            database_path,
            config.table,
        )

        source_count = len(rows)
        target_count = await postgres_count(
            connection,
            config.table,
        )

        status = (
            "PASS"
            if source_count == target_count
            else "FAIL"
        )

        if status == "FAIL":
            all_match = False

        print(
            f"{config.table:<28} "
            f"SQLite={source_count:<5} "
            f"Postgres={target_count:<5} "
            f"{status}"
        )

    return all_match


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate TitanAI SQLite persistence "
            "to PostgreSQL/Neon."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write to PostgreSQL.",
    )
    args = parser.parse_args()

    load_dotenv(
        dotenv_path=PROJECT_ROOT / ".env"
    )

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit(
            "DATABASE_URL_NOT_FOUND"
        )

    print("TitanAI SQLite -> PostgreSQL Migration")
    print("DATA_DIR =", DATA_DIR)
    print()

    print("SOURCE INVENTORY:")
    for config in TABLES:
        database_path = DATA_DIR / config.sqlite_file
        _, rows = read_sqlite_rows(
            database_path,
            config.table,
        )
        print(
            f" - {config.table:<28} "
            f"{len(rows)} rows "
            f"[{config.sqlite_file}]"
        )

    if not args.apply:
        print()
        print("DRY_RUN=PASS")
        print(
            "No PostgreSQL changes were made."
        )
        print(
            "Run again with --apply "
            "after reviewing the inventory."
        )
        return

    connection = await asyncpg.connect(
        database_url,
        timeout=30,
    )

    try:
        async with connection.transaction():
            print()
            print("=" * 72)
            print("MIGRATION")
            print("=" * 72)

            for config in TABLES:
                source_count, target_count = (
                    await migrate_table(
                        connection,
                        config,
                    )
                )

                if target_count != source_count:
                    raise RuntimeError(
                        "ROW_COUNT_MISMATCH "
                        f"table={config.table} "
                        f"source={source_count} "
                        f"target={target_count}"
                    )

            print()
            print("=" * 72)
            print("SEQUENCE SYNCHRONISATION")
            print("=" * 72)

            for config in TABLES:
                if config.sequence_column:
                    await sync_sequence(
                        connection,
                        config.table,
                        config.sequence_column,
                    )

            verified = await verify_all(
                connection
            )

            if not verified:
                raise RuntimeError(
                    "FINAL_VERIFICATION_FAILED"
                )

        print()
        print("SQLITE_TO_POSTGRES_MIGRATION=PASS")
        print(
            "Transaction committed successfully."
        )

    except Exception:
        print()
        print(
            "SQLITE_TO_POSTGRES_MIGRATION=FAIL"
        )
        print(
            "PostgreSQL transaction was rolled back."
        )
        raise

    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
