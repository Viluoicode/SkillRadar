"""CLI composition root — build the concrete adapters, inject them, run the pipeline.

Run:  python -m skillradar.interface.cli --trigger manual"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from skillradar.application.pipeline import PipelineDeps, run_pipeline
from skillradar.infrastructure.bronze.parquet_store import ParquetBronzeStore
from skillradar.infrastructure.config import Config, load_config
from skillradar.infrastructure.db.maintenance import export_serving_db
from skillradar.infrastructure.db.repositories import (
    DuckDbDemandRepository,
    DuckDbJobRepository,
    DuckDbRunRepository,
    DuckDbSkillLinkRepository,
)
from skillradar.infrastructure.db.warehouse import connect, ensure_schema
from skillradar.infrastructure.logging import configure_logging
from skillradar.infrastructure.skills.seed_loader import JsonSkillCatalog
from skillradar.infrastructure.sources.catalog import JsonBoardCatalog
from skillradar.infrastructure.sources.registry import HttpBoardFetcher


def build_pipeline(config: Config) -> tuple[PipelineDeps, duckdb.DuckDBPyConnection]:
    """Wire infrastructure adapters into the pipeline's ports. Caller owns the connection."""
    con = connect(config.duckdb_path)
    ensure_schema(con)
    deps = PipelineDeps(
        board_catalog=JsonBoardCatalog(config.sources_path),
        skill_catalog=JsonSkillCatalog(config.skills_path),
        fetcher=HttpBoardFetcher(config.delay_between_boards_ms),
        bronze=ParquetBronzeStore(config.bronze_dir),
        jobs=DuckDbJobRepository(con),
        links=DuckDbSkillLinkRepository(con),
        demand=DuckDbDemandRepository(con),
        runs=DuckDbRunRepository(con),
    )
    return deps, con


def _serving_db_path(config: Config) -> Path:
    """The committable serving DB sits next to the working warehouse as ``serving.duckdb``."""
    return config.duckdb_path.with_name("serving.duckdb")


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Run the SkillRadar Medallion pipeline.")
    parser.add_argument("--trigger", default="manual", help="Label recorded for this run.")
    parser.add_argument(
        "--export-serving",
        action="store_true",
        help="After the run, write a slim data/serving.duckdb (no descriptions) for deployment.",
    )
    args = parser.parse_args()

    config = load_config()
    deps, con = build_pipeline(config)
    try:
        result = run_pipeline(deps, trigger=args.trigger)
    finally:
        con.close()

    print(
        f"[{result.status}] run {result.run_id}: "
        f"{result.boards_succeeded}/{result.boards_attempted} boards, "
        f"{result.raw_fetched} raw, {result.jobs_upserted} jobs upserted, "
        f"{result.demand_rows} demand rows"
    )
    for err in result.errors:
        print("  ! ", err)

    if args.export_serving:
        dst = export_serving_db(config.duckdb_path, _serving_db_path(config))
        print(f"[serving] wrote {dst} ({dst.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
