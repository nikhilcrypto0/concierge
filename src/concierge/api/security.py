"""API-key authentication with two roles, and a per-key sliding-window rate limiter.

client   - a trusted backend (your web or mobile app server) that has already authenticated the
           customer and asserts their email. It can chat, nothing else.
operator - a support team member. It can list and decide approval requests, nothing else.

The rate limiter is in-process, which is correct for a single instance. Running several
replicas needs a shared store (Redis or Postgres) so limits hold across instances.
"""

import asyncio
import hmac
import math
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Literal

import structlog
from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from pydantic import SecretStr

Role = Literal["client", "operator"]
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class Principal:
    name: str
    role: Role


def authenticate(presented: str | None, keys: dict[str, SecretStr], role: Role) -> Principal | None:
    if not presented:
        return None
    match: Principal | None = None
    for name, key in keys.items():
        # Compare against every key so timing does not reveal which (or whether one) matched.
        if hmac.compare_digest(presented.encode(), key.get_secret_value().encode()):
            match = Principal(name, role)
    return match


class SlidingWindowRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> tuple[bool, float]:
        """Returns (allowed, seconds until the next request would be allowed)."""
        async with self._lock:
            now = self._clock()
            max_tracked_keys = 10_000
            if len(self._hits) > max_tracked_keys:
                # Bound memory when many distinct clients (e.g. failed-auth addresses) show up.
                idle = [k for k, q in self._hits.items() if not q or now - q[-1] >= self._window]
                for stale_key in idle:
                    del self._hits[stale_key]
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return False, self._window - (now - hits[0])
            hits.append(now)
            return True, 0.0


def require_role(role: Role) -> Callable[..., Awaitable[Principal]]:
    async def dependency(
        request: Request, api_key: Annotated[str | None, Security(API_KEY_HEADER)]
    ) -> Principal:
        settings = request.app.state.settings
        keys = settings.client_api_keys if role == "client" else settings.operator_api_keys
        limiter: SlidingWindowRateLimiter = request.app.state.rate_limiter
        principal = authenticate(api_key, keys, role)
        if principal is None:
            # Failed attempts are throttled per client address, so key guessing is limited too.
            client = request.client.host if request.client else "unknown"
            allowed, retry_after = await limiter.allow(f"unauthenticated:{client}")
            if not allowed:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="rate limit exceeded",
                    headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
                )
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="invalid or missing API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        allowed, retry_after = await limiter.allow(f"{role}:{principal.name}")
        if not allowed:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
                headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
            )
        structlog.contextvars.bind_contextvars(principal=principal.name, role=role)
        return principal

    return dependency
