"""HTTP client + resilience (httpx + tenacity).

Connectors do plain ``client.get`` so they stay easy to unit-test; the retry/backoff
policy is applied by the pipeline via :func:`fetch_with_retry`, which isolates transient
transport failures (the .NET equivalent was Polly on a typed ``HttpClient``)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

T = TypeVar("T")

USER_AGENT = "SkillRadar/0.1 (+https://github.com/; job-market intelligence, read-only)"


def build_client(timeout: float = 20.0) -> httpx.Client:
    """A shared httpx client. Connectors use absolute URLs, so no base_url is set."""
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )


def _is_retryable(exc: BaseException) -> bool:
    """Retry transient failures only: timeouts, connection blips, and 5xx responses.
    4xx responses (and parse errors) are not retried — they will not fix themselves."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


def fetch_with_retry[T](fn: Callable[[], T]) -> T:
    """Run ``fn`` with exponential backoff (3 attempts) on transient errors, reraising
    the last exception so the caller can isolate a failing board."""

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=8),
        reraise=True,
    )
    def _run() -> T:
        return fn()

    return _run()
