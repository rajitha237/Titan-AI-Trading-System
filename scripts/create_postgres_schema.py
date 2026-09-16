from __future__ import annotations

import asyncio
import os
import ssl
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.postgres_schema import metadata


def normalize_database_url(url: str) -> str:
    url = url.strip()

    if url.startswith("postgresql://"):
        url = url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    elif url.startswith("postgres://"):
        url = url.replace(
            "postgres://",
            "postgresql+asyncpg://",
            1,
        )

    parts = urlsplit(url)

    # asyncpg does not accept libpq URL arguments such as
    # sslmode or channel_binding as connect() keyword args.
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(
            parts.query,
            keep_blank_values=True,
        )
        if key not in {
            "sslmode",
            "channel_binding",
        }
    ]

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(filtered_query),
            parts.fragment,
        )
    )


async def main() -> None:
    load_dotenv()

    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        raise SystemExit("DATABASE_URL_NOT_FOUND")

    database_url = normalize_database_url(raw_url)

    ssl_context = ssl.create_default_context()

    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={
            "ssl": ssl_context,
        },
    )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

        print("POSTGRES_SCHEMA_CREATE=PASS")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
