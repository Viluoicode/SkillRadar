"""Prefect flow wrapping the Medallion pipeline (M6).

Install the orchestration extra first:  uv pip install -e ".[orchestration]"
Run:  python -m skillradar.interface.prefect_flow

The flow reuses the exact same use-case (``run_pipeline``) and adapters as the CLI — Prefect
adds scheduling, retries and observability without changing the pipeline logic. Connectors
already retry transient failures via tenacity; this adds a flow-level retry on top."""

from __future__ import annotations

from prefect import flow

from skillradar.application.dto import RunResult
from skillradar.application.pipeline import run_pipeline
from skillradar.infrastructure.config import load_config
from skillradar.infrastructure.logging import configure_logging
from skillradar.interface.cli import build_pipeline


@flow(name="skillradar-pipeline", retries=1, retry_delay_seconds=30)
def skillradar_flow(trigger: str = "prefect") -> RunResult:
    configure_logging()
    config = load_config()
    deps, con = build_pipeline(config)
    try:
        return run_pipeline(deps, trigger=trigger)
    finally:
        con.close()


if __name__ == "__main__":
    skillradar_flow()
