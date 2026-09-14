"""Integration fixtures: a real Postgres + pgvector database, rebuilt once per test session.

Set TEST_DATABASE_URL to point elsewhere. The database name must end in "_test": the session
starts by dropping its public schema, and that guard keeps a typo from wiping a real database.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from concierge.config import Settings
from concierge.db import DictPool, create_pool, run_migrations
from concierge.retrieval.embeddings import FastEmbedEmbedder
from concierge.retrieval.ingest import ingest

ROOT = Path(__file__).resolve().parents[2]
KB_DIR = ROOT / "data" / "kb"
SEED_SQL = (ROOT / "data" / "seed_bookings.sql").read_text()
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://localhost:5432/concierge_test"
)


def _database_reachable() -> bool:
    try:
        psycopg.connect(TEST_DATABASE_URL, connect_timeout=3).close()
    except psycopg.OperationalError:
        return False
    return True


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    reachable: bool | None = None
    for item in items:
        if "integration" not in item.path.parts:
            continue
        item.add_marker(pytest.mark.integration)
        if reachable is None:
            reachable = _database_reachable()
        if not reachable:
            item.add_marker(pytest.mark.skip(reason="no database at TEST_DATABASE_URL"))


@pytest.fixture(scope="session")
def embedder() -> FastEmbedEmbedder:
    settings = Settings(_env_file=None)
    return FastEmbedEmbedder(
        settings.embedding_model, settings.embedding_dimensions, settings.embedding_cache_dir
    )


async def _rebuild(database_url: str, embedder: FastEmbedEmbedder) -> None:
    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as conn:
        await conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        await conn.execute("CREATE SCHEMA public")
    pool = create_pool(database_url)
    await pool.open()
    try:
        async with pool.connection() as conn:
            await run_migrations(conn)
        await ingest(pool, embedder, KB_DIR)
    finally:
        await pool.close()


@pytest.fixture(scope="session")
def prepared_database(embedder: FastEmbedEmbedder) -> str:
    dbname = str(conninfo_to_dict(TEST_DATABASE_URL).get("dbname", ""))
    if not dbname.endswith("_test"):
        pytest.exit(f"refusing to reset database {dbname!r}: its name must end in _test")
    asyncio.run(_rebuild(TEST_DATABASE_URL, embedder))
    return TEST_DATABASE_URL


@pytest.fixture
def seeded(prepared_database: str) -> str:
    """Fresh demo bookings (and no approvals or conversations) for every test."""
    with psycopg.connect(prepared_database, autocommit=True) as conn:
        conn.execute(SEED_SQL.encode())
    return prepared_database


@pytest.fixture
async def pool(seeded: str) -> AsyncIterator[DictPool]:
    pool = create_pool(seeded, max_size=10)
    await pool.open()
    try:
        yield pool
    finally:
        await pool.close()
