"""Wire up connectors and fetch every curated board with per-board isolation.

A failing board is logged and skipped without aborting the run; a board counts as
"succeeded" only when its fetch completed, which the Silver step uses to decide whether to
deactivate that board's vanished postings (port of the .NET Bronze loop). All network,
retry and delay concerns live here so the application layer stays I/O-free."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence

import httpx

from skillradar.application.dto import BoardConfig, FetchOutcome
from skillradar.application.ports import JobSourceConnector
from skillradar.domain.models import JobSource
from skillradar.infrastructure.http.client import build_client, fetch_with_retry
from skillradar.infrastructure.sources.ashby import AshbyConnector
from skillradar.infrastructure.sources.greenhouse import GreenhouseConnector
from skillradar.infrastructure.sources.lever import LeverConnector

logger = logging.getLogger(__name__)


def build_registry(client: httpx.Client) -> dict[JobSource, JobSourceConnector]:
    return {
        JobSource.greenhouse: GreenhouseConnector(client),
        JobSource.lever: LeverConnector(client),
        JobSource.ashby: AshbyConnector(client),
    }


def fetch_all_boards(
    boards: Sequence[BoardConfig],
    registry: dict[JobSource, JobSourceConnector],
    delay_between_boards_ms: int = 500,
) -> FetchOutcome:
    outcome = FetchOutcome()
    delay = max(0, delay_between_boards_ms) / 1000.0
    first = True

    for board in boards:
        connector = registry.get(board.source)
        if connector is None:
            outcome.errors.append(f"{board.source.value}/{board.token}: no connector registered")
            continue

        # Polite delay between board calls to avoid hammering a source.
        if not first and delay > 0:
            time.sleep(delay)
        first = False

        try:
            jobs = fetch_with_retry(lambda c=connector, t=board.token: c.fetch(t))
            outcome.fetched.extend(jobs)
            outcome.succeeded_boards.add((board.source.value, board.token))
            logger.debug("Fetched %d from %s/%s", len(jobs), board.source.value, board.token)
        except Exception as exc:  # noqa: BLE001 — isolate any one board's failure
            outcome.errors.append(f"{board.source.value}/{board.token}: {exc}")
            logger.warning(
                "Board %s/%s failed; isolating and continuing: %s",
                board.source.value,
                board.token,
                exc,
            )

    return outcome


class HttpBoardFetcher:
    """Adapter implementing the ``BoardFetcher`` port over httpx connectors."""

    def __init__(self, delay_between_boards_ms: int = 500) -> None:
        self._delay_ms = delay_between_boards_ms

    def fetch_all(self, boards: Sequence[BoardConfig]) -> FetchOutcome:
        client = build_client()
        try:
            registry = build_registry(client)
            return fetch_all_boards(boards, registry, self._delay_ms)
        finally:
            client.close()
