"""Money-moving invariants, proven against real Postgres rather than assumed."""

import asyncio
from uuid import uuid4

import pytest

from concierge.bookings.repository import ApprovalRequest, RefundConflictError, SupportRepository
from concierge.db import DictPool

MAYA = "maya@example.com"


async def _approved(
    repo: SupportRepository, reference: str = "BK-1042", amount: int = 24_000
) -> ApprovalRequest:
    conversation_id = uuid4()
    assert await repo.claim_conversation(conversation_id, MAYA)
    request = await repo.open_approval_request(conversation_id, reference, amount, "full_notice")
    decided = await repo.decide_approval(request.id, approve=True, reviewer="lead", note=None)
    assert decided is not None
    return decided


async def _action_count(pool: DictPool, approval: ApprovalRequest) -> int:
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT count(*) AS n FROM actions WHERE approval_id = %s", (approval.id,)
        )
        row = await cur.fetchone()
    assert row is not None
    return int(row["n"])


async def test_refund_executes_exactly_once(pool: DictPool) -> None:
    repo = SupportRepository(pool)
    approval = await _approved(repo)
    assert await repo.execute_refund(approval.id) is True
    assert await repo.execute_refund(approval.id) is False
    booking = await repo.get_booking_for_customer("BK-1042", MAYA)
    assert booking is not None
    assert (booking.refunded_cents, booking.status) == (24_000, "cancelled")
    assert await _action_count(pool, approval) == 1


async def test_concurrent_executions_apply_the_refund_once(pool: DictPool) -> None:
    repo = SupportRepository(pool)
    approval = await _approved(repo)
    results = await asyncio.gather(*(repo.execute_refund(approval.id) for _ in range(5)))
    assert sorted(results) == [False, False, False, False, True]
    assert await _action_count(pool, approval) == 1


async def test_refund_requires_an_approved_request(pool: DictPool) -> None:
    repo = SupportRepository(pool)
    conversation_id = uuid4()
    await repo.claim_conversation(conversation_id, MAYA)
    pending = await repo.open_approval_request(conversation_id, "BK-1042", 24_000, "full_notice")
    with pytest.raises(PermissionError):
        await repo.execute_refund(pending.id)


async def test_only_one_of_two_simultaneous_decisions_wins(pool: DictPool) -> None:
    repo = SupportRepository(pool)
    conversation_id = uuid4()
    await repo.claim_conversation(conversation_id, MAYA)
    request = await repo.open_approval_request(conversation_id, "BK-1042", 24_000, "full_notice")
    outcomes = await asyncio.gather(
        repo.decide_approval(request.id, approve=True, reviewer="alice", note=None),
        repo.decide_approval(request.id, approve=False, reviewer="bob", note=None),
    )
    assert sum(o is not None for o in outcomes) == 1


async def test_opening_a_request_twice_returns_the_same_pending_request(pool: DictPool) -> None:
    repo = SupportRepository(pool)
    conversation_id = uuid4()
    await repo.claim_conversation(conversation_id, MAYA)
    first = await repo.open_approval_request(conversation_id, "BK-1042", 24_000, "full_notice")
    second = await repo.open_approval_request(conversation_id, "BK-1042", 24_000, "full_notice")
    assert first.id == second.id


async def test_refund_beyond_the_paid_amount_rolls_back(pool: DictPool) -> None:
    repo = SupportRepository(pool)
    approval = await _approved(repo, reference="BK-1046", amount=5_000)  # already fully refunded
    with pytest.raises(RefundConflictError):
        await repo.execute_refund(approval.id)
    assert await _action_count(pool, approval) == 0, "the audit row must roll back too"


async def test_bookings_and_conversations_are_scoped_to_their_owner(pool: DictPool) -> None:
    repo = SupportRepository(pool)
    assert await repo.get_booking_for_customer("BK-2001", MAYA) is None
    assert await repo.get_booking_for_customer("BK-1042", "MAYA@Example.com") is not None
    conversation_id = uuid4()
    assert await repo.claim_conversation(conversation_id, MAYA)
    assert not await repo.claim_conversation(conversation_id, "jordan@example.com")
    assert await repo.conversation_owner(conversation_id) == MAYA
