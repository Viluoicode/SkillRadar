"""Gold layer — aggregate skill demand per role per snapshot.

Port of the .NET ``AggregateSkillDemandAsync``: over the *active* jobs (deduplicated
cross-source by content hash), for each role count how many matching jobs require each
skill. Today's snapshot is replaced on each run; ``skill_trends`` accumulates snapshots."""

from __future__ import annotations

from datetime import datetime

import duckdb
import pandas as pd

from ..common.logging import get_logger
from .roles import DEFAULT_ROLES

logger = get_logger(__name__)


def aggregate_skill_demand(con: duckdb.DuckDBPyConnection, now: datetime) -> int:
    """Rebuild today's ``skill_demand`` (and append to ``skill_trends``). Returns row count."""
    today = now.date()
    snapshot = today.isoformat()

    jobs_df = con.execute("SELECT job_id, title, dedup_hash FROM jobs WHERE is_active").df()
    skills_df = con.execute("SELECT job_id, skill, category FROM job_skills").df()

    # Replace today's snapshot regardless of whether there are rows to write.
    con.execute("DELETE FROM skill_demand WHERE snapshot_date = ?", [today])
    con.execute("DELETE FROM skill_trends WHERE snapshot_date = ?", [today])

    if jobs_df.empty:
        logger.info("Gold: no active jobs; wrote 0 demand rows")
        return 0

    # Cross-source dedup: keep one job per content hash.
    jobs_df = jobs_df.drop_duplicates(subset="dedup_hash", keep="first")
    active_ids = set(jobs_df["job_id"])
    if not skills_df.empty:
        skills_df = skills_df[skills_df["job_id"].isin(active_ids)]

    titles_lower = jobs_df["title"].str.lower()
    rows: list[tuple[str, str, str, int, str]] = []

    for role_name, patterns in DEFAULT_ROLES:
        mask = titles_lower.apply(lambda t, p=patterns: any(pat in t for pat in p))
        matching_ids = set(jobs_df.loc[mask, "job_id"])
        if not matching_ids or skills_df.empty:
            continue

        sub = skills_df[skills_df["job_id"].isin(matching_ids)]
        if sub.empty:
            continue

        # Distinct skill per job, then count jobs per (skill, category).
        counts = sub.drop_duplicates(["job_id", "skill"]).groupby(
            ["skill", "category"], dropna=False
        ).size()
        for (skill, category), count in counts.items():
            rows.append((role_name, skill, category, int(count), snapshot))

    if rows:
        demand_df = pd.DataFrame(
            rows, columns=["role", "skill", "category", "job_count", "snapshot_date"]
        )
        con.register("demand_df", demand_df)
        try:
            con.execute(
                "INSERT INTO skill_demand "
                "SELECT role, skill, category, job_count, "
                "CAST(snapshot_date AS DATE) FROM demand_df"
            )
            con.execute(
                "INSERT INTO skill_trends "
                "SELECT role, skill, CAST(snapshot_date AS DATE), job_count FROM demand_df"
            )
        finally:
            con.unregister("demand_df")

    logger.info("Gold: wrote %d demand rows for %s", len(rows), snapshot)
    return len(rows)
