"""SkillRadar dashboard (Streamlit) — reads the Gold/Silver tables from DuckDB directly.

Run:  uv run streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# Make ``skillradar`` importable when running from the repo (src layout).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skillradar.common.config import load_config  # noqa: E402
from skillradar.common.db import connect  # noqa: E402

st.set_page_config(page_title="SkillRadar", page_icon="📡", layout="wide")
CONFIG = load_config()


@st.cache_resource
def get_connection():
    if not CONFIG.duckdb_path.exists():
        return None
    return connect(CONFIG.duckdb_path, read_only=True)


def query_df(sql: str, params: list | None = None) -> pd.DataFrame:
    con = get_connection()
    if con is None:
        return pd.DataFrame()
    return con.execute(sql, params or []).df()


def build_job_filters(skill, source, company, location, remote, search) -> tuple[str, list]:
    clauses = ["j.is_active"]
    params: list = []
    if skill and skill != "All":
        clauses.append("j.job_id IN (SELECT job_id FROM job_skills WHERE skill = ?)")
        params.append(skill)
    if source and source != "All":
        clauses.append("j.source = ?")
        params.append(source)
    if company:
        clauses.append("lower(j.company) LIKE ?")
        params.append(f"%{company.lower()}%")
    if location:
        clauses.append("lower(j.location) LIKE ?")
        params.append(f"%{location.lower()}%")
    if remote == "Remote only":
        clauses.append("j.is_remote = TRUE")
    elif remote == "On-site only":
        clauses.append("j.is_remote = FALSE")
    if search:
        clauses.append("lower(j.title) LIKE ?")
        params.append(f"%{search.lower()}%")
    return " AND ".join(clauses), params


def main() -> None:
    st.title("📡 SkillRadar")
    st.caption(
        "Real tech job postings from public ATS feeds (Greenhouse · Lever · Ashby), "
        "aggregated into in-demand skills per role. Read-only — every posting links to its source."
    )

    if get_connection() is None:
        st.warning(
            "No data yet. Run the pipeline first:\n\n"
            "```\nuv run python -m skillradar.pipeline.run\n```"
        )
        st.stop()

    # ---- Stats header ----
    stats = query_df(
        "SELECT (SELECT count(*) FROM jobs WHERE is_active) AS active_jobs, "
        "(SELECT count(DISTINCT skill) FROM job_skills) AS skills_seen, "
        "(SELECT max(finished_at) FROM ingestion_runs) AS last_run"
    )
    if not stats.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Active jobs", int(stats.at[0, "active_jobs"] or 0))
        c2.metric("Skills observed", int(stats.at[0, "skills_seen"] or 0))
        last_run = stats.at[0, "last_run"]
        c3.metric("Last run (UTC)", "—" if pd.isna(last_run) else str(last_run)[:16])

    # ---- Top skills per role ----
    st.header("Top in-demand skills")
    roles = query_df(
        "SELECT DISTINCT role FROM skill_demand "
        "WHERE snapshot_date = (SELECT max(snapshot_date) FROM skill_demand) ORDER BY role"
    )
    if roles.empty:
        st.info(
            "No skill-demand data yet — the latest run found no postings matching a role family."
        )
    else:
        col_a, col_b = st.columns([3, 1])
        role = col_a.selectbox("Role family", roles["role"].tolist())
        top_n = col_b.slider("Show top", min_value=5, max_value=40, value=20, step=5)
        demand = query_df(
            "SELECT skill, category, job_count FROM skill_demand "
            "WHERE role = ? AND snapshot_date = (SELECT max(snapshot_date) FROM skill_demand) "
            "ORDER BY job_count DESC, skill LIMIT ?",
            [role, top_n],
        )
        if demand.empty:
            st.info("No postings matched this role in the latest snapshot.")
        else:
            chart = (
                alt.Chart(demand)
                .mark_bar()
                .encode(
                    x=alt.X("job_count:Q", title="Postings requiring skill"),
                    y=alt.Y("skill:N", sort="-x", title=None),
                    color=alt.Color("category:N", title="Category"),
                    tooltip=["skill", "category", "job_count"],
                )
                .properties(height=max(300, 22 * len(demand)))
            )
            st.altair_chart(chart, use_container_width=True)

    # ---- Filterable job list ----
    st.header("Jobs")
    skills_opts = ["All"] + query_df(
        "SELECT DISTINCT skill FROM job_skills ORDER BY skill"
    )["skill"].tolist()
    source_opts = ["All"] + query_df(
        "SELECT DISTINCT source FROM jobs ORDER BY source"
    )["source"].tolist()

    f1, f2, f3 = st.columns(3)
    skill = f1.selectbox("Skill", skills_opts)
    source = f2.selectbox("Source", source_opts)
    remote = f3.selectbox("Remote", ["Any", "Remote only", "On-site only"])
    g1, g2, g3 = st.columns(3)
    company = g1.text_input("Company contains")
    location = g2.text_input("Location contains")
    search = g3.text_input("Title contains")

    where, params = build_job_filters(skill, source, company, location, remote, search)
    total = query_df(f"SELECT count(*) AS n FROM jobs j WHERE {where}", params)
    total_n = int(total.at[0, "n"]) if not total.empty else 0

    page_size = 25
    pages = max(1, (total_n + page_size - 1) // page_size)
    page = st.number_input(f"Page (of {pages}, {total_n} jobs)", 1, pages, 1) if total_n else 1
    offset = (page - 1) * page_size

    jobs = query_df(
        f"""
        SELECT j.company, j.title, j.location, j.is_remote, j.source, j.apply_url, j.posted_at,
               string_agg(s.skill, ', ' ORDER BY s.skill) AS skills
        FROM jobs j
        LEFT JOIN job_skills s ON j.job_id = s.job_id
        WHERE {where}
        GROUP BY j.company, j.title, j.location, j.is_remote, j.source, j.apply_url, j.posted_at
        ORDER BY j.posted_at DESC NULLS LAST
        LIMIT {page_size} OFFSET {offset}
        """,
        params,
    )
    if jobs.empty:
        st.info("No jobs match these filters.")
    else:
        st.dataframe(
            jobs,
            use_container_width=True,
            hide_index=True,
            column_config={
                "apply_url": st.column_config.LinkColumn("Apply", display_text="Open ↗"),
                "is_remote": st.column_config.CheckboxColumn("Remote"),
                "posted_at": st.column_config.DatetimeColumn("Posted", format="YYYY-MM-DD"),
            },
        )


if __name__ == "__main__":
    main()
