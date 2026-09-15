import pytest
from pydantic import SecretStr

from concierge.api.security import SlidingWindowRateLimiter, authenticate
from concierge.config import _parse_named_keys

KEYS = {"webapp": SecretStr("a" * 32), "mobile": SecretStr("b" * 32)}


def test_authenticate_returns_the_named_principal() -> None:
    principal = authenticate("b" * 32, KEYS, "client")
    assert principal is not None
    assert (principal.name, principal.role) == ("mobile", "client")


@pytest.mark.parametrize("presented", [None, "", "c" * 32, "a" * 31, "a" * 33])
def test_authenticate_rejects_anything_but_an_exact_key(presented: str | None) -> None:
    assert authenticate(presented, KEYS, "client") is None


async def test_rate_limiter_blocks_per_key_then_recovers() -> None:
    now = [0.0]
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60, clock=lambda: now[0])
    assert (await limiter.allow("webapp"))[0]
    assert (await limiter.allow("webapp"))[0]
    allowed, retry_after = await limiter.allow("webapp")
    assert not allowed
    assert retry_after == pytest.approx(60)
    assert (await limiter.allow("mobile"))[0], "limits are per key"
    now[0] = 60.0
    assert (await limiter.allow("webapp"))[0], "the window slides"


def test_key_parsing_accepts_named_pairs() -> None:
    keys = _parse_named_keys(f"webapp:{'x' * 16}, support-lead:{'y' * 20}")
    assert set(keys) == {"webapp", "support-lead"}
    assert keys["webapp"].get_secret_value() == "x" * 16


@pytest.mark.parametrize("raw", ["webapp:short", "no-colon-" + "x" * 20, ":" + "x" * 20])
def test_key_parsing_rejects_weak_or_malformed_keys(raw: str) -> None:
    with pytest.raises(ValueError):
        _parse_named_keys(raw)


async def test_rate_limiter_forgets_idle_clients_to_bound_memory() -> None:
    now = [0.0]
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, clock=lambda: now[0])
    for i in range(10_001):
        await limiter.allow(f"unauthenticated:10.0.{i // 256}.{i % 256}")
    now[0] = 120.0
    assert (await limiter.allow("webapp"))[0]
    assert len(limiter._hits) == 1
