"""Connection pool and a minimal, ordered SQL migration runner."""

import asyncio
from pathlib import Path

import structlog
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

log = structlog.get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

DictConnection = AsyncConnection[DictRow]
DictPool = AsyncConnectionPool[DictConnection]


def create_pool(database_url: str, min_size: int = 1, max_size: int = 10) -> DictPool:
    # autocommit + dict_row + prepare_threshold=0 are what the LangGraph Postgres checkpointer
    # requires; sharing one pool keeps the agent and the checkpointer on the same connections.
    return AsyncConnectionPool(
        conninfo=database_url,
        connection_class=DictConnection,
        min_size=min_size,
        max_size=max_size,
        open=False,
        kwargs={"autocommit": True, "row_factory": dict_row, "prepare_threshold": 0},
    )


def _read_migrations(migrations_dir: Path) -> list[tuple[str, str]]:
    return [(path.name, path.read_text()) for path in sorted(migrations_dir.glob("*.sql"))]


async def run_migrations(conn: DictConnection, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply every *.sql file not yet recorded, in filename order, each in its own transaction."""
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    cur = await conn.execute("SELECT name FROM schema_migrations")
    applied = {row["name"] for row in await cur.fetchall()}
    newly_applied: list[str] = []
    for name, sql in await asyncio.to_thread(_read_migrations, migrations_dir):
        if name in applied:
            continue
        async with conn.transaction():
            # Migration files hold many statements, which cannot be sent as a prepared statement.
            await conn.execute(sql.encode(), prepare=False)
            await conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (name,))
        log.info("migration.applied", name=name)
        newly_applied.append(name)
    return newly_applied
