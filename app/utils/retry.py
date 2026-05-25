"""
Retry utilities — equivalent of retry.ts.
Provides fixed-interval and exponential-backoff retry helpers.
"""

import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


async def retry_fixed(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    delay_ms: int = 5000,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    """Retry an async operation with a fixed delay between attempts."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                if on_retry:
                    on_retry(attempt, exc)
                await asyncio.sleep(delay_ms / 1000)
    raise last_error  # type: ignore


async def retry_exponential(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay_ms: int = 1000,
    max_delay_ms: int = 60000,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    """Retry with exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                if on_retry:
                    on_retry(attempt, exc)
                delay = min(base_delay_ms * (2 ** (attempt - 1)), max_delay_ms)
                await asyncio.sleep(delay / 1000)
    raise last_error  # type: ignore
