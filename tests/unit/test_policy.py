from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from concierge.bookings.models import Booking, BookingStatus
from concierge.bookings.policy import (
    FULL_REFUND_NOTICE,
    PARTIAL_REFUND_NOTICE,
    PARTIAL_REFUND_PERCENT,
    assess_refund,
)

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)


def booking(
    hours_ahead: float,
    amount: int = 20_000,
    status: BookingStatus = "scheduled",
    refunded: int = 0,
) -> Booking:
    return Booking(
        reference="BK-1042",
        customer_email="maya@example.com",
        service="Deep cleaning",
        scheduled_for=NOW + timedelta(hours=hours_ahead),
        amount_cents=amount,
        status=status,
        refunded_cents=refunded,
    )


@pytest.mark.parametrize(
    ("hours", "eligible", "amount", "reason"),
    [
        (120, True, 20_000, "full_notice"),
        (48, True, 20_000, "full_notice"),  # boundary is inclusive
        (47.9, True, 10_000, "partial_notice"),
        (24, True, 10_000, "partial_notice"),
        (23.9, False, 0, "late_notice"),
        (-5, False, 0, "late_notice"),  # appointment already started / no-show
    ],
)
def test_notice_windows(hours: float, eligible: bool, amount: int, reason: str) -> None:
    decision = assess_refund(booking(hours), NOW)
    assert (decision.eligible, decision.amount_cents, decision.reason) == (eligible, amount, reason)
    assert not decision.needs_human


def test_completed_service_goes_to_a_human() -> None:
    decision = assess_refund(booking(-48, status="completed"), NOW)
    assert not decision.eligible
    assert decision.needs_human
    assert decision.reason == "service_completed"


def test_fully_refunded_booking_is_not_refunded_again() -> None:
    decision = assess_refund(booking(120, status="cancelled", refunded=20_000), NOW)
    assert (decision.eligible, decision.reason) == (False, "already_refunded")


def test_partial_refund_never_exceeds_remaining_balance() -> None:
    decision = assess_refund(booking(30, amount=20_000, refunded=15_000), NOW)
    assert decision.amount_cents == 5_000


def test_policy_code_matches_the_published_help_article() -> None:
    """If someone edits the policy doc or the constants, this forces them to change both."""
    doc = (Path(__file__).resolve().parents[2] / "data" / "kb" / "refund-policy.md").read_text()
    assert FULL_REFUND_NOTICE == timedelta(hours=48)
    assert PARTIAL_REFUND_NOTICE == timedelta(hours=24)
    assert "48 hours or more before the appointment: full refund" in doc
    assert f"Between 24 and 48 hours before the appointment: {PARTIAL_REFUND_PERCENT}%" in doc
    assert "Less than 24 hours before the appointment: no refund" in doc
