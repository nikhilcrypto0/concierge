"""The database itself refuses a refund that no approval covers, even from a direct SQL write."""

from uuid import UUID, uuid4

import psycopg
import pytest

from concierge.bookings.repository import SupportRepository
from concierge.db import DictPool

MAYA = "maya@example.com"
FULL = 24_000  # BK-1042


async def _approval(pool: DictPool, approve: bool | None, lower: int | None = None) -> UUID:
    """An approval request for BK-1042: pending (None), approved (True) or rejected (False)."""
    repo = SupportRepository(pool)
    conversation_id = uuid4()
    assert await repo.claim_conversation(conversation_id, MAYA)
    request = await repo.open_approval_request(conversation_id, "BK-1042", FULL, "full_notice")
    if approve is not None:
        await repo.decide_approval(request.id, approve, "lead", None, lower)
    return request.id


def _insert_action(database_url: str, approval_id: UUID, amount: int,
                   booking: str = "BK-1042") -> None:
    """Straight SQL, bypassing every line of application code."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO actions (idempotency_key, approval_id, booking_reference, action,"
            " amount_cents) VALUES (%s, %s, %s, 'refund', %s)",
            (f"test:{uuid4()}", approval_id, booking, amount),
        )


async def test_an_action_for_a_pending_request_is_refused(pool: DictPool, seeded: str) -> None:
    approval_id = await _approval(pool, None)
    with pytest.raises(psycopg.errors.CheckViolation, match="approved approval"):
        _insert_action(seeded, approval_id, FULL)


async def test_an_action_for_a_rejected_request_is_refused(pool: DictPool, seeded: str) -> None:
    approval_id = await _approval(pool, False)
    with pytest.raises(psycopg.errors.CheckViolation, match="approved approval"):
        _insert_action(seeded, approval_id, FULL)


async def test_an_action_for_an_unknown_approval_is_refused(seeded: str) -> None:
    # The foreign key already refuses this; the trigger fires first with the clearer message.
    with pytest.raises((psycopg.errors.CheckViolation, psycopg.errors.ForeignKeyViolation)):
        _insert_action(seeded, uuid4(), FULL)


async def test_an_action_cannot_exceed_the_policy_amount(pool: DictPool, seeded: str) -> None:
    approval_id = await _approval(pool, True)
    _insert_action(seeded, approval_id, FULL)  # exactly the authorised amount is fine
    with pytest.raises(psycopg.errors.CheckViolation, match="authorised amount"):
        _insert_action(seeded, approval_id, FULL + 1)


async def test_an_action_cannot_exceed_a_reviewers_lower_amount(
    pool: DictPool, seeded: str
) -> None:
    approval_id = await _approval(pool, True, lower=10_000)
    _insert_action(seeded, approval_id, 10_000)
    with pytest.raises(psycopg.errors.CheckViolation, match="authorised amount"):
        _insert_action(seeded, approval_id, 10_001)  # within the policy amount, not the approval


async def test_an_action_must_target_the_approved_booking(pool: DictPool, seeded: str) -> None:
    approval_id = await _approval(pool, True)
    with pytest.raises(psycopg.errors.CheckViolation, match="booking its approval"):
        _insert_action(seeded, approval_id, 1_000, booking="BK-1043")


async def test_an_action_must_have_a_positive_amount(pool: DictPool, seeded: str) -> None:
    approval_id = await _approval(pool, True)
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert_action(seeded, approval_id, 0)
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert_action(seeded, approval_id, -500)


async def test_the_real_refund_path_still_works_under_the_trigger(
    pool: DictPool, seeded: str
) -> None:
    repo = SupportRepository(pool)
    approval_id = await _approval(pool, True, lower=10_000)
    assert await repo.execute_refund(approval_id) is True
    assert await repo.execute_refund(approval_id) is False  # exactly once, as before
    with psycopg.connect(seeded) as conn:
        row = conn.execute("SELECT count(*), sum(amount_cents) FROM actions").fetchone()
    assert row == (1, 10_000)
