"""Wire up connectors and fetch every curated board with per-board isolation.

A failing board is logged and skipped without aborting the run; a board counts as
"succeeded" only when its fetch completed, which the Silver step uses to decide whether
to deactivate that board's vanished postings (port of the .NET Bronze loop)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from ..common.http import fetch_with_retry
from ..common.logging import get_logger
from ..common.models import FetchedJob, JobSource
from .ashby import AshbyConnector
from .base import BoardConfig, JobSourceConnector
from .greenhouse import GreenhouseConnector
from .lever import LeverConnector

logger = get_logger(__name__)


def build_registry(client: httpx.Client) -> dict[JobSource, JobSourceConnector]:
    return {
        JobSource.greenhouse: GreenhouseConnector(client),
        JobSource.lever: LeverConnector(client),
        JobSource.ashby: AshbyConnector(client),
    }


@dataclass
class FetchOutcome:
    fetched: list[FetchedJob] = field(default_factory=list)
    # (source value, token) pairs whose fetch succeeded.
    succeeded_boards: set[tuple[str, str]] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)


def fetch_all_boards(
    boards: list[BoardConfig],
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
