"""Idempotent knowledge-base ingestion: only changed chunks are re-embedded, removed ones deleted.

Usage: uv run concierge-ingest [--kb-dir data/kb] [--seed-demo]
"""

import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path

import structlog

from concierge.config import get_settings
from concierge.db import DictPool, create_pool, run_migrations
from concierge.observability import configure_logging
from concierge.retrieval.chunking import load_directory
from concierge.retrieval.embeddings import Embedder, FastEmbedEmbedder, to_pgvector

log = structlog.get_logger(__name__)
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
DEFAULT_KB_DIR = DATA_DIR / "kb"
DEMO_SEED = DATA_DIR / "seed_bookings.sql"


@dataclass(frozen=True)
class IngestReport:
    upserted: int
    unchanged: int
    deleted: int


async def ingest(pool: DictPool, embedder: Embedder, kb_dir: Path) -> IngestReport:
    chunks = load_directory(kb_dir)
    if not chunks:
        raise ValueError(f"no markdown documents found in {kb_dir}")

    async with pool.connection() as conn:
        cur = await conn.execute("SELECT id, content_hash FROM kb_chunks")
        existing = {row["id"]: row["content_hash"] for row in await cur.fetchall()}

    changed = [c for c in chunks if existing.get(c.id) != c.content_hash]
    vectors = await embedder.embed_documents([c.embedding_text for c in changed]) if changed else []
    stale_ids = sorted(set(existing) - {c.id for c in chunks})

    async with pool.connection() as conn, conn.transaction():
        for chunk, vector in zip(changed, vectors, strict=True):
            await conn.execute(
                """
                INSERT INTO kb_chunks
                    (id, doc_slug, doc_title, heading, content, content_hash, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (id) DO UPDATE SET
                    doc_slug = EXCLUDED.doc_slug, doc_title = EXCLUDED.doc_title,
                    heading = EXCLUDED.heading, content = EXCLUDED.content,
                    content_hash = EXCLUDED.content_hash, embedding = EXCLUDED.embedding,
                    updated_at = now()
                """,
                (chunk.id, chunk.doc_slug, chunk.doc_title, chunk.heading, chunk.content,
                 chunk.content_hash, to_pgvector(vector)),
            )
        if stale_ids:
            await conn.execute("DELETE FROM kb_chunks WHERE id = ANY(%s)", (stale_ids,))

    report = IngestReport(len(changed), len(chunks) - len(changed), len(stale_ids))
    log.info(
        "kb.ingested",
        upserted=report.upserted,
        unchanged=report.unchanged,
        deleted=report.deleted,
    )
    return report


async def _main(kb_dir: Path, demo_seed_sql: str | None) -> None:
    settings = get_settings()
    pool = create_pool(settings.database_url)
    await pool.open()
    try:
        async with pool.connection() as conn:
            await run_migrations(conn)
        embedder = FastEmbedEmbedder(
            settings.embedding_model, settings.embedding_dimensions, settings.embedding_cache_dir
        )
        await ingest(pool, embedder, kb_dir)
        if demo_seed_sql is not None:
            async with pool.connection() as conn:
                await conn.execute(demo_seed_sql.encode(), prepare=False)
            log.warning("demo.seeded", note="bookings reset; conversations and approvals cleared")
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb-dir", type=Path, default=DEFAULT_KB_DIR)
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="reset demo bookings and clear conversations/approvals (refused in prod)",
    )
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=False)
    if args.seed_demo and settings.environment == "prod":
        parser.error("--seed-demo clears conversations and approvals; refusing in prod")
    demo_seed_sql = DEMO_SEED.read_text() if args.seed_demo else None
    asyncio.run(_main(args.kb_dir, demo_seed_sql))


if __name__ == "__main__":
    main()
