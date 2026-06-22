"""Prefect flow wrapping the Medallion steps (M6).

Install the orchestration extra first:  uv pip install -e ".[orchestration]"
Run:  uv run python -m skillradar.pipeline.flow

The flow reuses the exact same step functions as the plain runner in ``run.py`` — Prefect
adds retries, logging and observability without changing the pipeline logic."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from prefect import flow, task

from ..bronze.land import land_bronze
from ..common.config import Config, load_config
from ..common.db import connect, ensure_schema
from ..common.http import build_client
from ..gold.aggregate import aggregate_skill_demand
from ..ingestion.catalog import load_catalog
from ..ingestion.registry import build_registry, fetch_all_boards
from ..silver.normalize import upsert_jobs
from ..skills.dictionary import load_skills
from ..skills.extract import extract_job_skills
from .run import RunResult, _record_run, _status


@task(retries=2, retry_delay_seconds=10)
def fetch_task(config: Config):
    boards = load_catalog(config.sources_path)
    client = build_client()
    try:
        registry = build_registry(client)
        outcome = fetch_all_boards(boards, registry, config.delay_between_boards_ms)
    finally:
        client.close()
    return boards, outcome


@task
def transform_task(config: Config, outcome, started_at: datetime, run_id: str):
    con = connect(config.duckdb_path)
    try:
        ensure_schema(con)
        skills = load_skills(config.skills_path)
        land_bronze(outcome.fetched, run_id, started_at, config.bronze_dir)
        upserted, deactivated = upsert_jobs(
            con, outcome.fetched, outcome.succeeded_boards, started_at
        )
        extract_job_skills(con, upserted, skills)
        demand_rows = aggregate_skill_demand(con, started_at)
        return upserted, deactivated, demand_rows
    finally:
        con.close()


def run_id_for(started_at: datetime) -> str:
    return f"{started_at:%Y%m%d}-{uuid4().hex[:6]}"


@flow(name="skillradar-pipeline")
def skillradar_flow(trigger: str = "prefect") -> RunResult:
    config = load_config()
    started_at = datetime.now(UTC)
    run_id = run_id_for(started_at)

    boards, outcome = fetch_task(config)
    upserted, deactivated, demand_rows = transform_task(config, outcome, started_at, run_id)

    con = connect(config.duckdb_path)
    try:
        status = _status(outcome)
        _record_run(
            con,
            run_id=run_id,
            trigger=trigger,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            status=status,
            boards_attempted=len(boards),
            boards_succeeded=len(outcome.succeeded_boards),
            raw_fetched=len(outcome.fetched),
            jobs_upserted=len(upserted),
            jobs_deactivated=deactivated,
            errors=outcome.errors,
        )
    finally:
        con.close()

    return RunResult(
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


if __name__ == "__main__":
    skillradar_flow()
