"""Silver use-case — normalize, dedupe and upsert postings via a job repository."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime

from skillradar.application.ports import JobRepository
from skillradar.domain.models import FetchedJob
from skillradar.domain.reconciliation import reconcile_jobs

logger = logging.getLogger(__name__)


def upsert_jobs(
    repo: JobRepository,
    fetched: Sequence[FetchedJob],
    succeeded_boards: set[tuple[str, str]],
    now: datetime,
) -> tuple[list[str], int]:
    """Returns (job_ids touched this run, count deactivated)."""
    existing = repo.load_all()
    result = reconcile_jobs(existing, list(fetched), succeeded_boards, now)
    repo.save_all(result.jobs)
    logger.info(
        "Silver: %d upserted, %d deactivated (%d total)",
        len(result.upserted),
        result.deactivated,
        len(result.jobs),
    )
    return result.upserted, result.deactivated
