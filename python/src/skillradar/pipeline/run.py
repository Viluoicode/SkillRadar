"""Plain-Python orchestration of the Medallion pipeline for one run:
Bronze (fetch + land raw) -> Silver (normalize/dedupe/upsert) -> Gold (extract skills,
aggregate demand). Each board is isolated: a failing board is logged and skipped without
aborting the run. (M6 wraps these same steps in a Prefect flow.)"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import duckdb

from ..bronze.land import land_bronze
from ..common.config import Config, load_config
from ..common.db import connect, ensure_schema
from ..common.http import build_client
from ..common.logging import get_logger
from ..gold.aggregate import aggregate_skill_demand
from ..ingestion.catalog import load_catalog
from ..ingestion.registry import FetchOutcome, build_registry, fetch_all_boards
from ..silver.normalize import upsert_jobs
from ..skills.dictionary import load_skills

logger = get_logger(__name__)


@dataclass
class RunResult:
    run_id: str
    status: str
    boards_attempted: int
    boards_succeeded: int
    raw_fetched: int
    jobs_upserted: int
    jobs_deactivated: int
    demand_rows: int
    errors: list[str]


def _status(outcome: FetchOutcome) -> str:
    if not outcome.errors:
        return "succeeded"
    return "completed_with_errors" if outcome.succeeded_boards else "failed"


def _record_run(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    trigger: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    boards_attempted: int,
    boards_succeeded: int,
    raw_fetched: int,
    jobs_upserted: int,
    jobs_deactivated: int,
    errors: list[str],
) -> None:
    con.execute(
        """
        INSERT INTO ingestion_runs (
            run_id, trigger, started_at, finished_at, status,
            boards_attempted, boards_succeeded, raw_fetched,
            jobs_upserted, jobs_deactivated, errors
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            trigger,
            started_at,
            finished_at,
            status,
            boards_attempted,
            boards_succeeded,
            raw_fetched,
            jobs_upserted,
            jobs_deactivated,
            "\n".join(errors) if errors else None,
        ],
    )


def run_pipeline(config: Config | None = None, trigger: str = "manual") -> RunResult:
    config = config or load_config()
    started_at = datetime.now(UTC)
    run_id = uuid4().hex[:12]
    logger.info("Pipeline run %s starting (trigger=%s)", run_id, trigger)

    con = connect(config.duckdb_path)
    try:
        ensure_schema(con)
        boards = load_catalog(config.sources_path)
        skills = load_skills(config.skills_path)

        # ---- Bronze: fetch every board (isolated) and land raw payloads ----
        client = build_client()
        try:
            registry = build_registry(client)
            outcome = fetch_all_boards(boards, registry, config.delay_between_boards_ms)
        finally:
            client.close()
        land_bronze(outcome.fetched, run_id, started_at, config.bronze_dir)

        # ---- Silver: normalize, dedupe, lifecycle ----
        upserted, deactivated = upsert_jobs(
            con, outcome.fetched, outcome.succeeded_boards, started_at
        )

        # ---- Gold: extract skills + aggregate demand ----
        from ..skills.extract import extract_job_skills

        extract_job_skills(con, upserted, skills)
        demand_rows = aggregate_skill_demand(con, started_at)

        status = _status(outcome)
        finished_at = datetime.now(UTC)
        _record_run(
            con,
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

        result = RunResult(
            run_id=run_id,
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
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SkillRadar Medallion pipeline.")
    parser.add_argument("--trigger", default="manual", help="Label recorded for this run.")
    args = parser.parse_args()
    result = run_pipeline(trigger=args.trigger)
    print(
        f"[{result.status}] run {result.run_id}: "
        f"{result.boards_succeeded}/{result.boards_attempted} boards, "
        f"{result.raw_fetched} raw, {result.jobs_upserted} jobs upserted, "
        f"{result.demand_rows} demand rows"
    )
    for err in result.errors:
        print("  ! ", err)


if __name__ == "__main__":
    main()
