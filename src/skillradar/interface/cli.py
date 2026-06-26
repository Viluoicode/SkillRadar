"""CLI composition root — build the concrete adapters, inject them, run the pipeline.

Run:  python -m skillradar.interface.cli --trigger manual"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from skillradar.application.pipeline import PipelineDeps, run_pipeline
from skillradar.infrastructure.bronze.parquet_store import ParquetBronzeStore
from skillradar.infrastructure.config import Config, data_target, load_config
from skillradar.infrastructure.db.maintenance import export_serving_db
from skillradar.infrastructure.db.repositories import (
    DuckDbDemandRepository,
    DuckDbJobRepository,
    DuckDbRunRepository,
    DuckDbSkillLinkRepository,
)
from skillradar.infrastructure.db.warehouse import connect, ensure_schema
from skillradar.infrastructure.dbt.runner import dbt_available, run_dbt_gold
from skillradar.infrastructure.logging import configure_logging
from skillradar.infrastructure.skills.seed_loader import JsonSkillCatalog
from skillradar.infrastructure.sources.catalog import JsonBoardCatalog
from skillradar.infrastructure.sources.registry import HttpBoardFetcher


def build_pipeline(config: Config) -> tuple[PipelineDeps, duckdb.DuckDBPyConnection]:
    """Wire infrastructure adapters into the pipeline's ports. Caller owns the connection.

    Writes to MotherDuck in production (``MOTHERDUCK_TOKEN`` set) or a local DuckDB file in dev —
    see :func:`data_target`."""
    con = connect(data_target(config))
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


def _resolve_gold_engine(choice: str) -> str:
    """Pick the Silver→Gold builder. ``auto`` uses dbt when it's installed and the transform/
    project is present, else the Python fallback — so envs without dbt (e.g. a slim deploy) keep
    working. ``dbt`` / ``python`` force the choice."""
    if choice == "auto":
        return "dbt" if dbt_available() else "python"
    return choice


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Run the SkillRadar Medallion pipeline.")
    parser.add_argument("--trigger", default="manual", help="Label recorded for this run.")
    parser.add_argument(
        "--gold",
        choices=["auto", "dbt", "python"],
        default="auto",
        help="Silver-to-Gold engine: 'dbt' (the canonical transform + star schema), 'python' (the "
        "fallback aggregation), or 'auto' (dbt when available, else python). Default: auto.",
    )
    parser.add_argument(
        "--dbt-full-refresh",
        action="store_true",
        help="Pass --full-refresh to dbt (rebuild Gold tables from scratch). Only with --gold dbt.",
    )
    parser.add_argument(
        "--export-serving",
        action="store_true",
        help="After the run, write a slim data/serving.duckdb (no descriptions) for deployment.",
    )
    args = parser.parse_args()

    config = load_config()
    gold_engine = _resolve_gold_engine(args.gold)

    deps, con = build_pipeline(config)
    try:
        # In dbt mode, skip the Python Gold step — dbt builds it after we release the connection
        # (DuckDB is single-writer: a local file can't be open read-write here and by dbt at once).
        result = run_pipeline(deps, trigger=args.trigger, build_gold=(gold_engine == "python"))
    finally:
        con.close()

    if gold_engine == "dbt":
        target = data_target(config)
        run_dbt_gold(
            None if target.startswith("md:") else config.duckdb_path,
            result.started_at.date(),
            full_refresh=args.dbt_full_refresh,
        )

    gold_note = (
        f"{result.demand_rows} demand rows (python)"
        if gold_engine == "python"
        else "Gold built by dbt"
    )
    print(
        f"[{result.status}] run {result.run_id}: "
        f"{result.boards_succeeded}/{result.boards_attempted} boards, "
        f"{result.raw_fetched} raw, {result.jobs_upserted} jobs upserted, {gold_note}"
    )
    for err in result.errors:
        print("  ! ", err)

    if args.export_serving:
        if data_target(config).startswith("md:"):
            print("[serving] skipped — warehouse is MotherDuck (no local file to slim).")
        else:
            dst = export_serving_db(config.duckdb_path, _serving_db_path(config))
            print(f"[serving] wrote {dst} ({dst.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
