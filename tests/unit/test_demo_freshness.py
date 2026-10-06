"""The demo's staleness check leans on the seed file; these tests keep the two in sync."""

import re
from datetime import timedelta
from pathlib import Path

from concierge.api.app import DEMO_MAX_AGE
from concierge.bookings.policy import FULL_REFUND_NOTICE, PARTIAL_REFUND_NOTICE
from concierge.bookings.repository import DEMO_CLOCK_BOOKING, DEMO_CLOCK_LEAD

SEED = (Path(__file__).resolve().parents[2] / "data" / "seed_bookings.sql").read_text()


def _lead(reference: str) -> timedelta:
    match = re.search(rf"'{reference}'.*?now\(\) \+ interval '(\d+) (hours|days)'", SEED)
    assert match, f"{reference} is not seeded as 'now() + interval'"
    amount, unit = int(match.group(1)), match.group(2)
    return timedelta(**{unit: amount})


def test_the_clock_booking_matches_the_seed_file() -> None:
    assert _lead(DEMO_CLOCK_BOOKING) == DEMO_CLOCK_LEAD


def test_data_is_refreshed_before_any_refund_tier_drifts() -> None:
    # The 30-hour booking is meant to be a partial refund (24 to 48 hours of notice) and the
    # 6-hour one too late. After DEMO_MAX_AGE they must still be in those tiers, or the demo
    # would show the wrong outcome in the window before the refresh.
    partial = _lead("BK-1043") - DEMO_MAX_AGE
    assert PARTIAL_REFUND_NOTICE <= partial < FULL_REFUND_NOTICE
    assert _lead("BK-1044") < PARTIAL_REFUND_NOTICE
    assert _lead("BK-1042") - DEMO_MAX_AGE >= FULL_REFUND_NOTICE
