"""Refund policy as plain code. Money decisions are never delegated to a language model.

Mirrors data/kb/refund-policy.md; tests/unit/test_policy.py keeps the two in sync.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from concierge.bookings.models import Booking

FULL_REFUND_NOTICE = timedelta(hours=48)
PARTIAL_REFUND_NOTICE = timedelta(hours=24)
PARTIAL_REFUND_PERCENT = 50

RefundReason = Literal[
    "full_notice", "partial_notice", "late_notice", "already_refunded", "service_completed"
]


@dataclass(frozen=True)
class RefundDecision:
    eligible: bool
    amount_cents: int
    reason: RefundReason
    needs_human: bool

    @property
    def amount_display(self) -> str:
        return f"${self.amount_cents / 100:.2f}"


def assess_refund(booking: Booking, now: datetime) -> RefundDecision:
    if booking.refundable_cents <= 0:
        return RefundDecision(False, 0, "already_refunded", needs_human=False)
    if booking.status == "completed":
        # Post-service complaints need judgment about the work quality: route to a person.
        return RefundDecision(False, 0, "service_completed", needs_human=True)

    notice = booking.scheduled_for - now
    if notice >= FULL_REFUND_NOTICE:
        return RefundDecision(True, booking.refundable_cents, "full_notice", needs_human=False)
    if notice >= PARTIAL_REFUND_NOTICE:
        partial = booking.amount_cents * PARTIAL_REFUND_PERCENT // 100
        amount = min(partial, booking.refundable_cents)
        return RefundDecision(amount > 0, amount, "partial_notice", needs_human=False)
    return RefundDecision(False, 0, "late_notice", needs_human=False)
