"""Gold use-case — aggregate skill demand per role and replace today's snapshot."""

from __future__ import annotations

import logging
from datetime import datetime

from skillradar.application.ports import DemandRepository, JobRepository, SkillLinkRepository
from skillradar.domain.demand import aggregate_demand

logger = logging.getLogger(__name__)


def aggregate_skill_demand(
    job_repo: JobRepository,
    link_repo: SkillLinkRepository,
    demand_repo: DemandRepository,
    now: datetime,
) -> int:
    """Rebuild today's ``skill_demand`` (and append to ``skill_trends``). Returns row count."""
    snapshot = now.date()
    active = job_repo.active_jobs()
    links = link_repo.all_links()

    rows = aggregate_demand(active, links, snapshot)
    # Always replace today's snapshot, even when empty, so a run with no matches clears it.
    demand_repo.replace_snapshot(snapshot, rows)

    logger.info("Gold: wrote %d demand rows for %s", len(rows), snapshot.isoformat())
    return len(rows)
