"""All business-data access: bookings, conversations, approval requests, and the refund action.

Every write that moves money is idempotent and guarded by row-level preconditions in SQL, so a
retried request, a double-clicked approval, or a replayed graph step cannot refund twice.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

from concierge.bookings.models import Booking
from concierge.db import DictPool

ApprovalStatus = Literal["pending", "approved", "rejected"]

# data/seed_bookings.sql seeds this booking 30 hours ahead, so its time to go tells us how long
# ago the demo data was seeded. tests/unit/test_demo_freshness.py keeps the two in sync.
DEMO_CLOCK_BOOKING = "BK-1043"
DEMO_CLOCK_LEAD = timedelta(hours=30)


@dataclass(frozen=True)
class ApprovalRequest:
    id: UUID
    conversation_id: UUID
    booking_reference: str
    action: str
    amount_cents: int
    policy_reason: str
    status: ApprovalStatus
    reviewer: str | None
    review_note: str | None
    created_at: datetime
    decided_at: datetime | None
    customer_email: str | None = None  # present when the query joins conversations
    # What the reviewer actually authorised; None means the full policy amount.
    approved_amount_cents: int | None = None

    @property
    def authorised_cents(self) -> int:
        """The amount that may be refunded: never above the policy amount, by constraint."""
        return self.approved_amount_cents or self.amount_cents


class RefundConflictError(RuntimeError):
    """The booking no longer has enough refundable balance (changed since approval)."""


def _booking(row: dict[str, Any]) -> Booking:
    return Booking(**{k: row[k] for k in Booking.__dataclass_fields__})


def _approval(row: dict[str, Any]) -> ApprovalRequest:
    return ApprovalRequest(
        **{k: row[k] for k in ApprovalRequest.__dataclass_fields__ if k in row}
    )


class SupportRepository:
    def __init__(self, pool: DictPool) -> None:
        self._pool = pool

    async def get_booking_for_customer(self, reference: str, customer_email: str) -> Booking | None:
        """Ownership is part of the lookup: another customer's booking is simply "not found"."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT * FROM bookings WHERE reference = %s AND lower(customer_email) = lower(%s)",
                (reference, customer_email),
            )
            row = await cur.fetchone()
        return _booking(row) if row else None

    async def list_bookings_for_customer(self, customer_email: str) -> list[Booking]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT * FROM bookings WHERE lower(customer_email) = lower(%s)"
                " ORDER BY scheduled_for DESC",
                (customer_email,),
            )
            return [_booking(row) for row in await cur.fetchall()]

    async def get_booking(self, reference: str) -> Booking | None:
        """Operator lookup with no ownership filter. Never expose this to the customer role."""
        async with self._pool.connection() as conn:
            cur = await conn.execute("SELECT * FROM bookings WHERE reference = %s", (reference,))
            row = await cur.fetchone()
        return _booking(row) if row else None

    async def claim_conversation(self, conversation_id: UUID, customer_email: str) -> bool:
        """Create the conversation or confirm the caller owns it. False means someone else does."""
        async with self._pool.connection() as conn:
            await conn.execute(
                "INSERT INTO conversations (id, customer_email) VALUES (%s, %s)"
                " ON CONFLICT DO NOTHING",
                (conversation_id, customer_email),
            )
            cur = await conn.execute(
                "SELECT customer_email FROM conversations WHERE id = %s", (conversation_id,)
            )
            row = await cur.fetchone()
        return row is not None and str(row["customer_email"]).lower() == customer_email.lower()

    async def conversation_owner(self, conversation_id: UUID) -> str | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT customer_email FROM conversations WHERE id = %s", (conversation_id,)
            )
            row = await cur.fetchone()
        return str(row["customer_email"]) if row else None

    async def open_approval_request(
        self, conversation_id: UUID, booking_reference: str, amount_cents: int, policy_reason: str
    ) -> ApprovalRequest:
        async with self._pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO approval_requests
                    (id, conversation_id, booking_reference, action, amount_cents, policy_reason)
                VALUES (%s, %s, %s, 'refund', %s, %s)
                ON CONFLICT (conversation_id) WHERE status = 'pending' DO NOTHING
                """,
                (uuid4(), conversation_id, booking_reference, amount_cents, policy_reason),
            )
            cur = await conn.execute(
                "SELECT * FROM approval_requests WHERE conversation_id = %s AND status = 'pending'",
                (conversation_id,),
            )
            row = await cur.fetchone()
        if row is None:
            raise RuntimeError("approval request vanished between insert and select")
        return _approval(row)

    async def pending_approval_for(self, conversation_id: UUID) -> ApprovalRequest | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "SELECT * FROM approval_requests WHERE conversation_id = %s AND status = 'pending'",
                (conversation_id,),
            )
            row = await cur.fetchone()
        return _approval(row) if row else None

    async def get_approval(self, approval_id: UUID) -> ApprovalRequest | None:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT a.*, c.customer_email
                FROM approval_requests a JOIN conversations c ON c.id = a.conversation_id
                WHERE a.id = %s
                """,
                (approval_id,),
            )
            row = await cur.fetchone()
        return _approval(row) if row else None

    async def list_approvals(
        self, status: ApprovalStatus, limit: int = 50
    ) -> list[ApprovalRequest]:
        """Pending: oldest first (a queue). Decided: most recent decision first (a history)."""
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT a.*, c.customer_email
                FROM approval_requests a JOIN conversations c ON c.id = a.conversation_id
                WHERE a.status = %(status)s
                ORDER BY CASE WHEN %(status)s::text = 'pending' THEN a.created_at END ASC,
                         a.decided_at DESC NULLS LAST
                LIMIT %(limit)s
                """,
                {"status": status, "limit": limit},
            )
            return [_approval(row) for row in await cur.fetchall()]

    async def decide_approval(
        self, approval_id: UUID, approve: bool, reviewer: str, note: str | None,
        approved_amount_cents: int | None = None,
    ) -> ApprovalRequest | None:
        """Atomic pending -> decided transition. None if already decided or never existed.

        `approved_amount_cents` authorises less than the policy amount. The database refuses
        anything above the policy amount, or any amount on a rejection.
        """
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                UPDATE approval_requests
                SET status = %s, reviewer = %s, review_note = %s, decided_at = now(),
                    approved_amount_cents = %s
                WHERE id = %s AND status = 'pending'
                RETURNING *
                """,
                ("approved" if approve else "rejected", reviewer, note,
                 approved_amount_cents, approval_id),
            )
            row = await cur.fetchone()
        return _approval(row) if row else None

    async def execute_refund(self, approval_id: UUID) -> bool:
        """Apply an approved refund exactly once. Returns False if it had already been applied."""
        async with self._pool.connection() as conn, conn.transaction():
            cur = await conn.execute(
                "SELECT * FROM approval_requests WHERE id = %s AND status = 'approved' FOR UPDATE",
                (approval_id,),
            )
            approval = await cur.fetchone()
            if approval is None:
                raise PermissionError("refund requires an approved approval request")
            authorised = approval["approved_amount_cents"] or approval["amount_cents"]
            cur = await conn.execute(
                """
                INSERT INTO actions
                    (idempotency_key, approval_id, booking_reference, action, amount_cents)
                VALUES (%s, %s, %s, 'refund', %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING idempotency_key
                """,
                (f"refund:{approval_id}", approval_id, approval["booking_reference"],
                 authorised),
            )
            if await cur.fetchone() is None:
                return False
            cur = await conn.execute(
                """
                UPDATE bookings
                SET refunded_cents = refunded_cents + %(amount)s,
                    status = CASE WHEN status = 'scheduled' THEN 'cancelled' ELSE status END
                WHERE reference = %(ref)s AND refunded_cents + %(amount)s <= amount_cents
                RETURNING reference
                """,
                {"amount": authorised, "ref": approval["booking_reference"]},
            )
            if await cur.fetchone() is None:
                raise RefundConflictError(approval["booking_reference"])
        return True

    async def demo_data_is_stale(
        self, max_age: timedelta, quiet_for: timedelta, pending_grace: timedelta
    ) -> bool:
        """True when the demo bookings are old enough that their refund tiers have drifted.

        Seeded times are relative to the moment of seeding (a booking "6 hours away" stops being
        late-notice once that time passes). Reseeding wipes conversations, so it only counts as
        due when nobody is mid-demo: no chat for `quiet_for` and no refund that was requested
        within `pending_grace` and is still waiting for a person. A request nobody has touched
        for longer than that is abandoned, and must not freeze the demo data forever.
        """
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT
                    (SELECT now() - (scheduled_for - %(lead)s) FROM bookings
                     WHERE reference = %(ref)s) AS age,
                    (SELECT count(*) FROM approval_requests
                     WHERE status = 'pending' AND created_at > now() - %(grace)s) AS pending,
                    (SELECT now() - max(created_at) FROM llm_usage) AS idle
                """,
                {"ref": DEMO_CLOCK_BOOKING, "lead": DEMO_CLOCK_LEAD, "grace": pending_grace},
            )
            row = await cur.fetchone()
        if row is None or row["age"] is None:
            return False  # nothing seeded here, so there is nothing to refresh
        recently_active = row["idle"] is not None and row["idle"] < quiet_for
        return row["age"] >= max_age and row["pending"] == 0 and not recently_active

    async def reset_demo_data(self, seed_sql: str) -> None:
        """Restore demo bookings and forget every conversation, approval, and checkpoint.

        The token ledger (llm_usage) is deliberately kept: resetting the demo must not reset
        the daily spending budget.
        """
        async with self._pool.connection() as conn, conn.transaction():
            await conn.execute(seed_sql.encode(), prepare=False)
            await conn.execute("DELETE FROM checkpoint_writes")
            await conn.execute("DELETE FROM checkpoint_blobs")
            await conn.execute("DELETE FROM checkpoints")
