"""The Medallion pipeline use-case: Bronze (fetch + land) → Silver (normalize/dedupe/upsert)
→ Gold (extract skills, aggregate demand). It depends only on ports, so the composition
root decides which concrete adapters (DuckDB, httpx, JSON catalogs) to inject."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from skillradar.application import ports
from skillradar.application.dto import FetchOutcome, RunRecord, RunResult
from skillradar.application.services import gold, silver
from skillradar.application.services import skills as skills_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineDeps:
    """The adapters the pipeline needs, all behind ports (wired at the composition root)."""

    board_catalog: ports.BoardCatalog
    skill_catalog: ports.SkillCatalog
    fetcher: ports.BoardFetcher
    bronze: ports.BronzeStore
    jobs: ports.JobRepository
    links: ports.SkillLinkRepository
    demand: ports.DemandRepository
    runs: ports.RunRepository


def _status(outcome: FetchOutcome) -> str:
    if not outcome.errors:
        return "succeeded"
    return "completed_with_errors" if outcome.succeeded_boards else "failed"


def run_pipeline(deps: PipelineDeps, trigger: str = "manual", build_gold: bool = True) -> RunResult:
    started_at = datetime.now(UTC)
    run_id = uuid4().hex[:12]
    logger.info("Pipeline run %s starting (trigger=%s)", run_id, trigger)

    boards = deps.board_catalog.load()
    skill_defs = deps.skill_catalog.load()

    # ---- Bronze: fetch every board (isolated) and land raw payloads ----
    outcome = deps.fetcher.fetch_all(boards)
    deps.bronze.land(outcome.fetched, run_id, started_at)

    # ---- Silver: normalize, dedupe, lifecycle ----
    upserted, deactivated = silver.upsert_jobs(
        deps.jobs, outcome.fetched, outcome.succeeded_boards, started_at
    )

    # ---- Gold: extract skills, then aggregate demand ----
    # Skill extraction always runs in Python — it writes ``job_skills``, the input the dbt staging
    # models read. The demand aggregation is built either here (the Python fallback) or by dbt
    # after the pipeline's write connection closes (``build_gold=False``; see interface/cli.py and
    # infrastructure/dbt/runner.py). Either way the output is identical — guaranteed by
    # tests/test_dbt_parity.py.
    skills_service.extract_job_skills(deps.jobs, deps.links, upserted, skill_defs)
    demand_rows = (
        gold.aggregate_skill_demand(deps.jobs, deps.links, deps.demand, started_at)
        if build_gold
        else 0
    )

    status = _status(outcome)
    finished_at = datetime.now(UTC)
    deps.runs.record(
        RunRecord(
            run_id=run_id,
            trigger=trigger,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            boards_attempted=len(boards),
            boards_succeeded=len(outcome.succeeded_boards),
            raw_fetched=len(outcome.fetched),
            jobs_upserted=len(upserted),
            jobs_deactivated=deactivated,
            errors=outcome.errors,
        )
    )

    result = RunResult(
        run_id=run_id,
        started_at=started_at,
        status=status,
        boards_attempted=len(boards),
        boards_succeeded=len(outcome.succeeded_boards),
        raw_fetched=len(outcome.fetched),
        jobs_upserted=len(upserted),
        jobs_deactivated=deactivated,
        demand_rows=demand_rows,
        errors=outcome.errors,
    )
    logger.info(
        "Pipeline run %s %s: %d/%d boards, %d raw, %d upserted, %d deactivated, %d demand rows",
        run_id,
        status,
        result.boards_succeeded,
        result.boards_attempted,
        result.raw_fetched,
        result.jobs_upserted,
        result.jobs_deactivated,
        result.demand_rows,
    )
    return result
