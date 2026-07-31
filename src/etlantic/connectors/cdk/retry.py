"""Bounded backoff for classified retryable connector errors."""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import anyio

from etlantic.connectors.errors import ConnectorError

T = TypeVar("T")

# Codes that are safe to retry (throttling / transient I/O).
DEFAULT_RETRYABLE_CODES: frozenset[str] = frozenset(
    {
        "PMCONN_RETRY",
        "PMCONN_THROTTLE",
        "PMCONN_TRANSIENT",
    }
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded exponential backoff policy."""

    max_attempts: int = 3
    initial_backoff_seconds: float = 0.05
    max_backoff_seconds: float = 2.0
    multiplier: float = 2.0
    jitter: float = 0.1
    honor_retry_after: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_backoff_seconds < 0:
            raise ValueError("initial_backoff_seconds must be >= 0")


def is_retryable_error(
    exc: BaseException,
    *,
    retryable_codes: frozenset[str] | None = None,
) -> bool:
    """Classify whether *exc* is safe to retry."""
    if getattr(exc, "retryable", False) is True:
        return True
    codes = retryable_codes if retryable_codes is not None else DEFAULT_RETRYABLE_CODES
    if isinstance(exc, ConnectorError):
        if exc.code and exc.code in codes:
            return True
        details = exc.details or {}
        if details.get("retryable") is True:
            return True
        status = details.get("status") or details.get("http_status")
        if status in {408, 425, 429, 500, 502, 503, 504}:
            return True
    return False


def retry_after_seconds(exc: BaseException) -> float | None:
    """Extract Retry-After / retry_after hint when present."""
    if isinstance(exc, ConnectorError):
        details = exc.details or {}
        for key in ("retry_after", "Retry-After", "retry_after_seconds"):
            if key in details and details[key] is not None:
                try:
                    return max(0.0, float(details[key]))
                except (TypeError, ValueError):
                    return None
    raw = getattr(exc, "retry_after", None)
    if raw is not None:
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            return None
    return None


def compute_backoff(
    attempt: int,
    policy: RetryPolicy,
    *,
    retry_after: float | None = None,
) -> float:
    """Compute sleep seconds for the given 0-based failed attempt index."""
    if policy.honor_retry_after and retry_after is not None:
        return min(float(retry_after), policy.max_backoff_seconds)
    base = policy.initial_backoff_seconds * (policy.multiplier**attempt)
    capped = min(base, policy.max_backoff_seconds)
    if policy.jitter <= 0:
        return capped
    spread = capped * policy.jitter
    return max(0.0, capped + random.uniform(-spread, spread))


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy | None = None,
    retryable_codes: frozenset[str] | None = None,
    on_retry: Callable[[BaseException, int, float], Any] | None = None,
) -> T:
    """Await *func* with bounded retries for classified retryable errors."""
    policy = policy or RetryPolicy()
    last_exc: BaseException | None = None
    for attempt in range(policy.max_attempts):
        try:
            return await func()
        except BaseException as exc:
            last_exc = exc
            if attempt + 1 >= policy.max_attempts or not is_retryable_error(
                exc, retryable_codes=retryable_codes
            ):
                raise
            delay = compute_backoff(
                attempt,
                policy,
                retry_after=retry_after_seconds(exc),
            )
            if on_retry is not None:
                on_retry(exc, attempt + 1, delay)
            if delay > 0:
                await anyio.sleep(delay)
    assert last_exc is not None
    raise last_exc


__all__ = [
    "DEFAULT_RETRYABLE_CODES",
    "RetryPolicy",
    "compute_backoff",
    "is_retryable_error",
    "retry_after_seconds",
    "retry_async",
]
