"""SkillRadar dashboard (Streamlit) — presentation only.

All SQL lives in ``DuckDbServingReadModel`` (infrastructure); this module just builds
filter state and renders charts/tables. Run:  streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# Make ``skillradar`` importable when running from the repo (src layout).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skillradar.infrastructure.config import load_config  # noqa: E402
from skillradar.infrastructure.db.repositories import (  # noqa: E402
    DuckDbServingReadModel,
    JobFilters,
)
from skillradar.infrastructure.db.warehouse import connect  # noqa: E402

st.set_page_config(page_title="SkillRadar", page_icon="📡", layout="wide")
CONFIG = load_config()
PAGE_SIZE = 25


@st.cache_resource
def get_read_model() -> DuckDbServingReadModel | None:
    if not CONFIG.duckdb_path.exists():
        return None
    return DuckDbServingReadModel(connect(CONFIG.duckdb_path, read_only=True))


def main() -> None:
    st.title("📡 SkillRadar")
    st.caption(
        "Real tech job postings from public ATS feeds (Greenhouse · Lever · Ashby), "
        "aggregated into in-demand skills per role. Read-only — every posting links to its source."
    )

    read_model = get_read_model()
    if read_model is None:
        st.warning(
            "No data yet. Run the pipeline first:\n\n"
            "```\npython -m skillradar.interface.cli\n```"
        )
        st.stop()

    # ---- Stats header ----
    stats = read_model.stats()
    if not stats.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Active jobs", int(stats.at[0, "active_jobs"] or 0))
        c2.metric("Skills observed", int(stats.at[0, "skills_seen"] or 0))
        last_run = stats.at[0, "last_run"]
        c3.metric("Last run (UTC)", "—" if pd.isna(last_run) else str(last_run)[:16])

    # ---- Top skills per role ----
    st.header("Top in-demand skills")
    roles = read_model.roles_latest()
    if roles.empty:
        st.info(
            "No skill-demand data yet — the latest run found no postings matching a role family."
        )
    else:
        col_a, col_b = st.columns([3, 1])
        role = col_a.selectbox("Role family", roles["role"].tolist())
        top_n = col_b.slider("Show top", min_value=5, max_value=40, value=20, step=5)
        demand = read_model.demand(role, top_n)
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
    skills_opts = ["All"] + read_model.distinct_skills()
    source_opts = ["All"] + read_model.distinct_sources()

    f1, f2, f3 = st.columns(3)
    skill = f1.selectbox("Skill", skills_opts)
    source = f2.selectbox("Source", source_opts)
    remote = f3.selectbox("Remote", ["Any", "Remote only", "On-site only"])
    g1, g2, g3 = st.columns(3)
    company = g1.text_input("Company contains")
    location = g2.text_input("Location contains")
    search = g3.text_input("Title contains")

    filters = JobFilters(
        skill=skill,
        source=source,
        company=company,
        location=location,
        remote=remote,
        search=search,
    )
    total_n = read_model.job_count(filters)

    pages = max(1, (total_n + PAGE_SIZE - 1) // PAGE_SIZE)
    page = st.number_input(f"Page (of {pages}, {total_n} jobs)", 1, pages, 1) if total_n else 1
    offset = (page - 1) * PAGE_SIZE

    jobs = read_model.jobs_page(filters, PAGE_SIZE, offset)
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
