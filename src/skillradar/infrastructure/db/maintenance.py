"""Warehouse maintenance — produce a slim, committable serving database.

The working ``skillradar.duckdb`` accumulates rewrite bloat (repeated DELETE+INSERT) and stores
full job descriptions the dashboard never reads. :func:`export_serving_db` copies every table into
a *fresh* file (which reclaims the bloat) and blanks ``jobs.description``, yielding a few-MB file
small enough to commit so Streamlit Community Cloud can serve it.

The result is read-only by intent: ``CREATE TABLE AS SELECT`` drops PK/NOT NULL constraints, but
the serving read model only issues SELECTs."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from skillradar.infrastructure.db.warehouse import JOB_COLUMNS

logger = logging.getLogger(__name__)

# Tables copied verbatim (jobs is handled separately to blank the description column).
_COPY_VERBATIM = ("job_skills", "skill_demand", "skill_trends", "ingestion_runs")


def _sql_str(path: Path) -> str:
    """Quote a path for inline use in a DuckDB statement (forward slashes work on Windows)."""
    return "'" + path.as_posix().replace("'", "''") + "'"


def export_serving_db(src_path: str | Path, dst_path: str | Path) -> Path:
    """Write a compact, description-free copy of ``src_path`` to ``dst_path`` and return it.

    Every table is recreated in a fresh database, so the output carries none of the source's
    free-space bloat. ``jobs.description`` is replaced with empty strings — it is a pipeline-time
    input only, never surfaced by the dashboard."""
    src_path = Path(src_path)
    dst_path = Path(dst_path)
    if not src_path.exists():
        raise FileNotFoundError(f"source warehouse not found: {src_path}")

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    # Start from a clean file so we never inherit prior bloat or a stale WAL.
    for p in (dst_path, dst_path.with_name(dst_path.name + ".wal")):
        p.unlink(missing_ok=True)

    job_select = ", ".join("'' AS description" if c == "description" else c for c in JOB_COLUMNS)

    con = duckdb.connect(str(dst_path))
    try:
        con.execute(f"ATTACH {_sql_str(src_path)} AS src (READ_ONLY)")
        con.execute(f"CREATE TABLE jobs AS SELECT {job_select} FROM src.jobs")
        for table in _COPY_VERBATIM:
            con.execute(f"CREATE TABLE {table} AS SELECT * FROM src.{table}")
        con.execute("DETACH src")
        con.execute("CHECKPOINT")
    finally:
        con.close()

    size_mb = dst_path.stat().st_size / 1e6
    logger.info("Exported serving DB → %s (%.1f MB)", dst_path, size_mb)
    return dst_path
