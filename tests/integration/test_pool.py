"""The pool must survive the database dropping its connections (Neon suspends idle computes)."""

import asyncio

import psycopg

from concierge.db import create_pool

from .conftest import TEST_DATABASE_URL


async def test_pool_replaces_a_connection_the_server_closed() -> None:
    pool = create_pool(TEST_DATABASE_URL, min_size=1, max_size=2)
    await pool.open(wait=True)
    try:
        async with pool.connection() as conn:
            cur = await conn.execute("SELECT pg_backend_pid() AS pid")
            row = await cur.fetchone()
        assert row is not None

        async with await psycopg.AsyncConnection.connect(
            TEST_DATABASE_URL, autocommit=True
        ) as admin:
            await admin.execute("SELECT pg_terminate_backend(%s)", (row["pid"],))
        await asyncio.sleep(0.2)

        async with pool.connection() as conn:
            cur = await conn.execute("SELECT 1 AS ok")
            assert await cur.fetchone() == {"ok": 1}
    finally:
        await pool.close()
