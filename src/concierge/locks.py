"""Per-conversation mutual exclusion, correct across API replicas (Postgres advisory lock).

Two requests for one conversation (a double-submit, a client retry, a chat racing an approval
decision) must never run the graph on the same LangGraph thread at the same time. The lock is
non-blocking: the second request gets a 409 and retries, instead of queueing behind a slow
model call. If the holding connection dies, Postgres releases the lock with the session.

A lock holds one connection for as long as the model call takes, so locks live in their own
pool. Sharing the work pool would let a handful of slow chats take every connection and leave
none for the queries those chats need to finish. When the lock pool is full, the caller is told
the conversation is busy, the same answer as a lost race, rather than left waiting.
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from uuid import UUID

from psycopg_pool import PoolTimeout

from concierge.db import DictPool

_LOCK_SQL = "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked"
_UNLOCK_SQL = "SELECT pg_advisory_unlock(hashtextextended(%s, 0))"


@asynccontextmanager
async def conversation_lock(
    pool: DictPool, conversation_id: UUID, wait_seconds: float = 2.0
) -> AsyncIterator[bool]:
    """Yields True if this caller now holds the conversation, False if it is busy."""
    key = f"conversation:{conversation_id}"
    async with AsyncExitStack() as stack:
        try:
            conn = await stack.enter_async_context(pool.connection(timeout=wait_seconds))
        except PoolTimeout:
            yield False
            return
        cur = await conn.execute(_LOCK_SQL, (key,))
        row = await cur.fetchone()
        locked = bool(row and row["locked"])
        try:
            yield locked
        finally:
            if locked:
                await conn.execute(_UNLOCK_SQL, (key,))
