"""DuckDB connection + schema. DuckDB is the embedded analytical warehouse holding the
Silver, Gold and meta tables. (Bronze lives as Parquet files on disk — replayable.)"""

from __future__ import annotations

from pathlib import Path

import duckdb

# Column order matches the ``jobs`` DDL below; repositories rely on it for SELECT */INSERT.
JOB_COLUMNS = [
    "job_id",
    "source",
    "source_job_id",
    "board_token",
    "company",
    "title",
    "location",
    "is_remote",
    "description",
    "apply_url",
    "posted_at",
    "dedup_hash",
    "first_seen_at",
    "last_seen_at",
    "is_active",
]

# Silver — one row per posting, deduped, with lifecycle columns.
_JOBS_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id        TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    source_job_id TEXT NOT NULL,
    board_token   TEXT NOT NULL,
    company       TEXT NOT NULL,
    title         TEXT NOT NULL,
    location      TEXT,
    is_remote     BOOLEAN NOT NULL DEFAULT FALSE,
    description   TEXT NOT NULL DEFAULT '',
    apply_url     TEXT NOT NULL DEFAULT '',
    posted_at     TIMESTAMPTZ,
    dedup_hash    TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at  TIMESTAMPTZ NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);
"""

# Silver — extracted skills per job (canonical skill name + category).
_JOB_SKILLS_DDL = """
CREATE TABLE IF NOT EXISTS job_skills (
    job_id   TEXT NOT NULL,
    skill    TEXT NOT NULL,
    category TEXT
);
"""

# Gold — demand per role per snapshot.
_SKILL_DEMAND_DDL = """
CREATE TABLE IF NOT EXISTS skill_demand (
    role          TEXT NOT NULL,
    skill         TEXT NOT NULL,
    category      TEXT,
    job_count     INTEGER NOT NULL,
    snapshot_date DATE NOT NULL
);
"""

# Gold — accumulated daily snapshots for trend charts.
_SKILL_TRENDS_DDL = """
CREATE TABLE IF NOT EXISTS skill_trends (
    role          TEXT NOT NULL,
    skill         TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    job_count     INTEGER NOT NULL
);
"""

# Meta — per-run observability.
_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id            TEXT PRIMARY KEY,
    trigger           TEXT,
    started_at        TIMESTAMPTZ NOT NULL,
    finished_at       TIMESTAMPTZ,
    status            TEXT,
    boards_attempted  INTEGER DEFAULT 0,
    boards_succeeded  INTEGER DEFAULT 0,
    raw_fetched       INTEGER DEFAULT 0,
    jobs_upserted     INTEGER DEFAULT 0,
    jobs_deactivated  INTEGER DEFAULT 0,
    errors            TEXT
);
"""

_ALL_DDL = (_JOBS_DDL, _JOB_SKILLS_DDL, _SKILL_DEMAND_DDL, _SKILL_TRENDS_DDL, _RUNS_DDL)


def connect(path: str | Path, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open (and create) the DuckDB warehouse at ``path``."""
    path = Path(path)
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    for ddl in _ALL_DDL:
        con.execute(ddl)
