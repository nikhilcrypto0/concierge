"""Token budgets: per conversation and per rolling 24 hours, checked before every model call.

A breach halts the AI step, logs loudly for the operator, and hands the customer to a human.
The check-then-call sequence is a soft ceiling: concurrent calls can overshoot by one call.
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol
from uuid import UUID

import structlog

from concierge.db import DictPool

log = structlog.get_logger(__name__)

BudgetScope = Literal["conversation", "day"]


class BudgetExceededError(RuntimeError):
    def __init__(self, scope: BudgetScope, used: int, limit: int) -> None:
        super().__init__(f"{scope} token budget exceeded: {used}/{limit}")
        self.scope = scope
        self.used = used
        self.limit = limit


class UsageLedger(Protocol):
    async def check(self, conversation_id: UUID) -> None: ...

    async def record(
        self, conversation_id: UUID, step: str, model: str, input_tokens: int, output_tokens: int
    ) -> None: ...


def _enforce(conversation_used: int, day_used: int, per_conversation: int, per_day: int) -> None:
    if conversation_used >= per_conversation:
        raise BudgetExceededError("conversation", conversation_used, per_conversation)
    if day_used >= per_day:
        raise BudgetExceededError("day", day_used, per_day)


class PostgresUsageLedger:
    def __init__(self, pool: DictPool, per_conversation: int, per_day: int) -> None:
        self._pool = pool
        self._per_conversation = per_conversation
        self._per_day = per_day

    async def check(self, conversation_id: UUID) -> None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT
                    COALESCE(SUM(input_tokens + output_tokens)
                        FILTER (WHERE conversation_id = %(cid)s), 0) AS conversation_used,
                    COALESCE(SUM(input_tokens + output_tokens)
                        FILTER (WHERE created_at >= now() - interval '24 hours'), 0) AS day_used
                FROM llm_usage
                WHERE conversation_id = %(cid)s OR created_at >= now() - interval '24 hours'
                """,
                {"cid": conversation_id},
            )
            row = await cur.fetchone()
        assert row is not None
        _enforce(int(row["conversation_used"]), int(row["day_used"]),
                 self._per_conversation, self._per_day)

    async def record(
        self, conversation_id: UUID, step: str, model: str, input_tokens: int, output_tokens: int
    ) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "INSERT INTO llm_usage (conversation_id, step, model, input_tokens, output_tokens)"
                " VALUES (%s, %s, %s, %s, %s)",
                (conversation_id, step, model, input_tokens, output_tokens),
            )
        log.info("llm.usage", step=step, model=model, input_tokens=input_tokens,
                 output_tokens=output_tokens)


@dataclass
class InMemoryUsageLedger:
    """For tests and evals that must not touch the shared ledger."""

    per_conversation: int
    per_day: int
    entries: list[tuple[UUID, str, str, int, int]] = field(default_factory=list)

    async def check(self, conversation_id: UUID) -> None:
        conversation_used = sum(i + o for cid, _, _, i, o in self.entries if cid == conversation_id)
        day_used = sum(i + o for _, _, _, i, o in self.entries)
        _enforce(conversation_used, day_used, self.per_conversation, self.per_day)

    async def record(
        self, conversation_id: UUID, step: str, model: str, input_tokens: int, output_tokens: int
    ) -> None:
        self.entries.append((conversation_id, step, model, input_tokens, output_tokens))
