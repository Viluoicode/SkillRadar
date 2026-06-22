"""DuckDB implementations of the application persistence ports.

Every SQL statement in the pipeline lives here. The services and domain never see a query
string or a DuckDB connection — they speak in domain records, and these adapters translate
to/from the warehouse tables defined in :mod:`skillradar.infrastructure.db.warehouse`."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import duckdb
import pandas as pd

from skillradar.application.dto import RunRecord
from skillradar.domain.records import ActiveJob, DemandRow, JobRecord, JobText, SkillLink
from skillradar.infrastructure.db.warehouse import JOB_COLUMNS


def _opt(value: object) -> object | None:
    """Normalize pandas NULLs (None / NaN / NaT) to ``None``."""
    return None if pd.isna(value) else value


def _dt(value: object) -> datetime | None:
    value = _opt(value)
    if value is None:
        return None
    return value.to_pydatetime() if hasattr(value, "to_pydatetime") else value


# --------------------------------------------------------------------------- jobs (Silver)
class DuckDbJobRepository:
    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self._con = con

    def load_all(self) -> list[JobRecord]:
        df = self._con.execute(f"SELECT {', '.join(JOB_COLUMNS)} FROM jobs").df()
        return [
            JobRecord(
                job_id=r["job_id"],
                source=r["source"],
                source_job_id=r["source_job_id"],
                board_token=r["board_token"],
                company=r["company"],
                title=r["title"],
                location=_opt(r["location"]),
                is_remote=bool(r["is_remote"]),
                description=r["description"],
                apply_url=r["apply_url"],
                posted_at=_dt(r["posted_at"]),
                dedup_hash=r["dedup_hash"],
                first_seen_at=_dt(r["first_seen_at"]),
                last_seen_at=_dt(r["last_seen_at"]),
                is_active=bool(r["is_active"]),
            )
            for r in df.to_dict("records")
        ]

    def save_all(self, jobs: Sequence[JobRecord]) -> None:
        """Rewrite the ``jobs`` table from the given records, preserving its schema."""
        rows = [{col: getattr(j, col) for col in JOB_COLUMNS} for j in jobs]
        df = pd.DataFrame(rows, columns=JOB_COLUMNS)
        for col in ("posted_at", "first_seen_at", "last_seen_at"):
            df[col] = pd.to_datetime(df[col], utc=True)
        for col in ("is_remote", "is_active"):
            df[col] = df[col].astype(bool)

        self._con.register("jobs_df", df)
        try:
            self._con.execute("DELETE FROM jobs")
            self._con.execute("INSERT INTO jobs SELECT * FROM jobs_df")
        finally:
            self._con.unregister("jobs_df")

    def active_jobs(self) -> list[ActiveJob]:
        df = self._con.execute(
            "SELECT job_id, title, dedup_hash FROM jobs WHERE is_active"
        ).df()
        return [
            ActiveJob(r["job_id"], r["title"], r["dedup_hash"]) for r in df.to_dict("records")
        ]

    def texts_for(self, job_ids: Sequence[str]) -> list[JobText]:
        ids = list(dict.fromkeys(job_ids))
        if not ids:
            return []
        self._con.register("ids_df", pd.DataFrame({"job_id": ids}))
        try:
            df = self._con.execute(
                "SELECT job_id, title, description FROM jobs "
                "WHERE job_id IN (SELECT job_id FROM ids_df)"
            ).df()
        finally:
            self._con.unregister("ids_df")
        return [JobText(r["job_id"], r["title"], r["description"]) for r in df.to_dict("records")]

    def all_texts(self) -> list[JobText]:
        df = self._con.execute("SELECT job_id, title, description FROM jobs").df()
        return [JobText(r["job_id"], r["title"], r["description"]) for r in df.to_dict("records")]


# ----------------------------------------------------------------------- job_skills (Silver)
class DuckDbSkillLinkRepository:
    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self._con = con

    def all_links(self) -> list[SkillLink]:
        df = self._con.execute("SELECT job_id, skill, category FROM job_skills").df()
        return [
            SkillLink(r["job_id"], r["skill"], _opt(r["category"])) for r in df.to_dict("records")
        ]

    def replace_for(self, job_ids: Sequence[str], links: Sequence[SkillLink]) -> None:
        ids = list(dict.fromkeys(job_ids))
        if ids:
            self._con.register("ids_df", pd.DataFrame({"job_id": ids}))
            try:
                self._con.execute(
                    "DELETE FROM job_skills WHERE job_id IN (SELECT job_id FROM ids_df)"
                )
            finally:
                self._con.unregister("ids_df")
        self._insert(links)

    def replace_all(self, links: Sequence[SkillLink]) -> None:
        self._con.execute("DELETE FROM job_skills")
        self._insert(links)

    def _insert(self, links: Sequence[SkillLink]) -> None:
        if not links:
            return
        df = pd.DataFrame(
            [(link.job_id, link.skill, link.category) for link in links],
            columns=["job_id", "skill", "category"],
        )
        self._con.register("links_df", df)
        try:
            self._con.execute("INSERT INTO job_skills SELECT * FROM links_df")
        finally:
            self._con.unregister("links_df")


# ------------------------------------------------------------- skill_demand / trends (Gold)
class DuckDbDemandRepository:
    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self._con = con

    def replace_snapshot(self, snapshot_date: date, rows: Sequence[DemandRow]) -> None:
        self._con.execute("DELETE FROM skill_demand WHERE snapshot_date = ?", [snapshot_date])
        self._con.execute("DELETE FROM skill_trends WHERE snapshot_date = ?", [snapshot_date])
        if not rows:
            return
        df = pd.DataFrame(
            [
                (r.role, r.skill, r.category, r.job_count, r.snapshot_date.isoformat())
                for r in rows
            ],
            columns=["role", "skill", "category", "job_count", "snapshot_date"],
        )
        self._con.register("demand_df", df)
        try:
            self._con.execute(
                "INSERT INTO skill_demand "
                "SELECT role, skill, category, job_count, "
                "CAST(snapshot_date AS DATE) FROM demand_df"
            )
            self._con.execute(
                "INSERT INTO skill_trends "
                "SELECT role, skill, CAST(snapshot_date AS DATE), job_count FROM demand_df"
            )
        finally:
            self._con.unregister("demand_df")


# ---------------------------------------------------------------- ingestion_runs (meta)
class DuckDbRunRepository:
    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self._con = con

    def record(self, run: RunRecord) -> None:
        self._con.execute(
            """
            INSERT INTO ingestion_runs (
                run_id, trigger, started_at, finished_at, status,
                boards_attempted, boards_succeeded, raw_fetched,
                jobs_upserted, jobs_deactivated, errors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run.run_id,
                run.trigger,
                run.started_at,
                run.finished_at,
                run.status,
                run.boards_attempted,
                run.boards_succeeded,
                run.raw_fetched,
                run.jobs_upserted,
                run.jobs_deactivated,
                "\n".join(run.errors) if run.errors else None,
            ],
        )


# ----------------------------------------------------------------- serving read model
@dataclass
class JobFilters:
    """The filter state for the dashboard job list. ``"All"``/empty means no constraint."""

    skill: str | None = None
    source: str | None = None
    company: str | None = None
    location: str | None = None
    remote: str = "Any"  # "Any" | "Remote only" | "On-site only"
    search: str | None = None


class DuckDbServingReadModel:
    """Read-only queries that back the Streamlit dashboard. Returns pandas frames so the
    presentation layer can render charts/tables without touching SQL."""

    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self._con = con

    def stats(self) -> pd.DataFrame:
        return self._con.execute(
            "SELECT (SELECT count(*) FROM jobs WHERE is_active) AS active_jobs, "
            "(SELECT count(DISTINCT skill) FROM job_skills) AS skills_seen, "
            "(SELECT max(finished_at) FROM ingestion_runs) AS last_run"
        ).df()

    def roles_latest(self) -> pd.DataFrame:
        return self._con.execute(
            "SELECT DISTINCT role FROM skill_demand "
            "WHERE snapshot_date = (SELECT max(snapshot_date) FROM skill_demand) ORDER BY role"
        ).df()

    def demand(self, role: str, top_n: int) -> pd.DataFrame:
        return self._con.execute(
            "SELECT skill, category, job_count FROM skill_demand "
            "WHERE role = ? AND snapshot_date = (SELECT max(snapshot_date) FROM skill_demand) "
            "ORDER BY job_count DESC, skill LIMIT ?",
            [role, top_n],
        ).df()

    def trends(self, role: str, top_n: int) -> pd.DataFrame:
        """Demand over time for a role's current top-``top_n`` skills (from ``skill_trends``).
        Picks the leaders by the latest snapshot, then returns their full daily history."""
        return self._con.execute(
            """
            WITH latest AS (
                SELECT skill FROM skill_trends
                WHERE role = ? AND snapshot_date = (
                    SELECT max(snapshot_date) FROM skill_trends WHERE role = ?
                )
                ORDER BY job_count DESC, skill
                LIMIT ?
            )
            SELECT t.snapshot_date, t.skill, t.job_count
            FROM skill_trends t
            JOIN latest l ON t.skill = l.skill
            WHERE t.role = ?
            ORDER BY t.snapshot_date, t.skill
            """,
            [role, role, top_n, role],
        ).df()

    def distinct_skills(self) -> list[str]:
        return self._con.execute(
            "SELECT DISTINCT skill FROM job_skills ORDER BY skill"
        ).df()["skill"].tolist()

    def distinct_sources(self) -> list[str]:
        return self._con.execute(
            "SELECT DISTINCT source FROM jobs ORDER BY source"
        ).df()["source"].tolist()

    def job_count(self, f: JobFilters) -> int:
        where, params = self._where(f)
        df = self._con.execute(f"SELECT count(*) AS n FROM jobs j WHERE {where}", params).df()
        return int(df.at[0, "n"]) if not df.empty else 0

    def jobs_page(self, f: JobFilters, limit: int, offset: int) -> pd.DataFrame:
        where, params = self._where(f)
        return self._con.execute(
            f"""
            SELECT j.company, j.title, j.location, j.is_remote, j.source, j.apply_url,
                   j.posted_at, string_agg(s.skill, ', ' ORDER BY s.skill) AS skills
            FROM jobs j
            LEFT JOIN job_skills s ON j.job_id = s.job_id
            WHERE {where}
            GROUP BY j.company, j.title, j.location, j.is_remote, j.source, j.apply_url,
                     j.posted_at
            ORDER BY j.posted_at DESC NULLS LAST
            LIMIT {int(limit)} OFFSET {int(offset)}
            """,
            params,
        ).df()

    @staticmethod
    def _where(f: JobFilters) -> tuple[str, list]:
        clauses = ["j.is_active"]
        params: list = []
        if f.skill and f.skill != "All":
            clauses.append("j.job_id IN (SELECT job_id FROM job_skills WHERE skill = ?)")
            params.append(f.skill)
        if f.source and f.source != "All":
            clauses.append("j.source = ?")
            params.append(f.source)
        if f.company:
            clauses.append("lower(j.company) LIKE ?")
            params.append(f"%{f.company.lower()}%")
        if f.location:
            clauses.append("lower(j.location) LIKE ?")
            params.append(f"%{f.location.lower()}%")
        if f.remote == "Remote only":
            clauses.append("j.is_remote = TRUE")
        elif f.remote == "On-site only":
            clauses.append("j.is_remote = FALSE")
        if f.search:
            clauses.append("lower(j.title) LIKE ?")
            params.append(f"%{f.search.lower()}%")
        return " AND ".join(clauses), params
