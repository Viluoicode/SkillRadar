"""Silver layer — normalize, dedupe and upsert postings into the DuckDB ``jobs`` table.

Port of the .NET ``NormalizeToSilverAsync``:
* dedup key ``(source, source_job_id)``;
* cross-source dedup — a brand-new posting that duplicates an *active* job owned by a
  different source (same content hash) is skipped;
* lifecycle — ``first_seen_at`` / ``last_seen_at`` / ``is_active``; a posting is
  deactivated only when it vanished from a board that fetched successfully this run.
"""

from __future__ import annotations

from datetime import datetime

import duckdb
import pandas as pd

from ..common.dedup import compute_dedup_hash, make_job_id
from ..common.logging import get_logger
from ..common.models import FetchedJob

logger = get_logger(__name__)

# Column order matches the ``jobs`` DDL in common/db.py.
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


def _apply_fields(row: dict, f: FetchedJob, dedup_hash: str, now: datetime) -> None:
    row["board_token"] = f.board_token
    row["source_job_id"] = f.source_job_id
    row["company"] = f.company
    row["title"] = f.title
    row["location"] = f.location
    row["is_remote"] = bool(f.remote)
    row["description"] = f.description or ""
    row["apply_url"] = f.apply_url or ""
    row["posted_at"] = f.posted_at
    row["dedup_hash"] = dedup_hash
    row["last_seen_at"] = now
    row["is_active"] = True


def upsert_jobs(
    con: duckdb.DuckDBPyConnection,
    fetched: list[FetchedJob],
    succeeded_boards: set[tuple[str, str]],
    now: datetime,
) -> tuple[list[str], int]:
    """Returns (job_ids touched this run, count deactivated)."""
    existing = con.execute(f"SELECT {', '.join(JOB_COLUMNS)} FROM jobs").df().to_dict("records")
    jobs: dict[str, dict] = {r["job_id"]: dict(r) for r in existing}
    by_source_id = {(r["source"], r["source_job_id"]): r["job_id"] for r in existing}

    # Owner of each dedup hash among currently active jobs (for cross-source dedup).
    active_hash_owner: dict[str, tuple[str, str]] = {}
    for r in existing:
        if bool(r["is_active"]):
            active_hash_owner.setdefault(r["dedup_hash"], (r["source"], r["source_job_id"]))

    seen_keys: set[tuple[str, str]] = set()
    upserted: list[str] = []

    for f in fetched:
        key = (f.source.value, f.source_job_id)
        if key in seen_keys:
            continue  # same posting appeared twice in this run
        seen_keys.add(key)

        dedup_hash = compute_dedup_hash(f.company, f.title, f.location)

        if key in by_source_id:
            jid = by_source_id[key]
            _apply_fields(jobs[jid], f, dedup_hash, now)
            active_hash_owner[dedup_hash] = key
            upserted.append(jid)
        else:
            owner = active_hash_owner.get(dedup_hash)
            if owner is not None and owner[0] != f.source.value:
                logger.debug(
                    "Skipping cross-source duplicate %s/%s (hash owned by %s)",
                    f.source.value,
                    f.source_job_id,
                    owner[0],
                )
                continue
            jid = make_job_id(f.source.value, f.source_job_id)
            row = {"job_id": jid, "source": f.source.value, "first_seen_at": now}
            _apply_fields(row, f, dedup_hash, now)
            jobs[jid] = row
            by_source_id[key] = jid
            active_hash_owner[dedup_hash] = key
            upserted.append(jid)

    # Deactivate postings that vanished from boards we successfully fetched.
    deactivated = 0
    for r in jobs.values():
        if not bool(r["is_active"]):
            continue
        if (r["source"], r["board_token"]) not in succeeded_boards:
            continue  # board failed or not in catalog — leave untouched
        if (r["source"], r["source_job_id"]) not in seen_keys:
            r["is_active"] = False
            deactivated += 1

    _write_jobs(con, list(jobs.values()))
    return upserted, deactivated


def _write_jobs(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    """Rewrite the ``jobs`` table from the in-memory rows, preserving its schema."""
    jobs_df = pd.DataFrame(rows, columns=JOB_COLUMNS)
    for col in ("posted_at", "first_seen_at", "last_seen_at"):
        jobs_df[col] = pd.to_datetime(jobs_df[col], utc=True)
    for col in ("is_remote", "is_active"):
        jobs_df[col] = jobs_df[col].astype(bool)

    con.register("jobs_df", jobs_df)
    try:
        con.execute("DELETE FROM jobs")
        con.execute("INSERT INTO jobs SELECT * FROM jobs_df")
    finally:
        con.unregister("jobs_df")
