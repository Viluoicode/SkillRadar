"""SkillRadar dashboard (Streamlit) — presentation only.

All SQL lives in ``DuckDbServingReadModel`` (infrastructure) and all gap logic in
``skillradar.domain.skillgap``; this module just builds filter state and renders. Run:
  streamlit run dashboard/app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# Make ``skillradar`` importable when running from the repo (src layout).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skillradar.domain.skillgap import DemandedSkill, compute_skill_gap  # noqa: E402
from skillradar.domain.skills.dictionary import build_matcher  # noqa: E402
from skillradar.infrastructure.ai.anthropic_roadmap import AnthropicRoadmapGenerator  # noqa: E402
from skillradar.infrastructure.ai.market_chat import MarketChatAgent  # noqa: E402
from skillradar.infrastructure.config import data_target, load_config  # noqa: E402
from skillradar.infrastructure.db.repositories import (  # noqa: E402
    DuckDbServingReadModel,
    JobFilters,
)
from skillradar.infrastructure.db.warehouse import connect  # noqa: E402
from skillradar.infrastructure.skills.seed_loader import JsonSkillCatalog  # noqa: E402

st.set_page_config(page_title="SkillRadar", page_icon="📡", layout="wide")
CONFIG = load_config()
PAGE_SIZE = 25
# Set on a hosted deployment (e.g. Streamlit Cloud). Hides the in-app Refresh button — the
# container's filesystem is ephemeral, so data is refreshed by the scheduled CI pipeline instead.
SERVE_ONLY = bool(os.environ.get("SKILLRADAR_SERVE_ONLY"))


def _api_key() -> str | None:
    """The Anthropic key for AI features: the one pasted into the sidebar this session, else the
    ``ANTHROPIC_API_KEY`` env var. Bring-your-own-key keeps a public deploy free for the owner."""
    return st.session_state.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")


@st.cache_resource
def get_read_model() -> DuckDbServingReadModel | None:
    """Read model over the warehouse — MotherDuck in production, a local DuckDB file in dev.
    Returns ``None`` only for local dev when no file exists yet (prompts a Refresh)."""
    target = data_target(CONFIG)
    if not target.startswith("md:") and not Path(target).exists():
        return None
    return DuckDbServingReadModel(connect(target, read_only=True))


@st.cache_resource
def get_matcher():
    """The skill matcher + an id→name map, built from the same dictionary the pipeline uses,
    so a user's pasted skills are parsed exactly like a job description."""
    skills = JsonSkillCatalog(CONFIG.skills_path).load()
    return build_matcher(skills), {s.skill_id: s.name for s in skills}


def get_roadmap_generator() -> AnthropicRoadmapGenerator:
    """Built per run (not cached) so it picks up the session's bring-your-own-key. Lightweight —
    it only holds the model name, cache dir, and key."""
    return AnthropicRoadmapGenerator(
        model=CONFIG.llm_model, cache_dir=CONFIG.roadmap_cache_dir, api_key=_api_key()
    )


def _refresh_data():
    """Run Bronze→Silver→Gold in-process, then drop cached connections so the dashboard reloads
    fresh data. The read-only connection is released first — DuckDB can't hold read-only and
    read-write handles to the same file at once within a process."""
    from skillradar.application.pipeline import run_pipeline
    from skillradar.interface.cli import build_pipeline

    existing = get_read_model()
    if existing is not None:
        existing.close()
    get_read_model.clear()

    deps, con = build_pipeline(CONFIG)
    try:
        return run_pipeline(deps, trigger="dashboard")
    finally:
        con.close()


def render_sidebar() -> None:
    with st.sidebar:
        st.subheader("Data")
        if SERVE_ONLY:
            st.caption("Data refreshes daily via the scheduled pipeline (GitHub Actions).")
        else:
            st.caption(
                "Pull the latest postings from every board and re-extract skills (~1–2 min)."
            )
            if st.button("🔄 Refresh data", use_container_width=True):
                try:
                    with st.spinner("Fetching latest jobs from all boards…"):
                        result = _refresh_data()
                except Exception as exc:  # surface source/network errors instead of crashing
                    st.error(f"Refresh failed: {exc}")
                else:
                    st.toast(
                        f"Refreshed: {result.jobs_upserted} jobs, {result.demand_rows} demand rows",
                        icon="✅",
                    )
                    st.rerun()

        st.divider()
        st.subheader("AI features")
        st.caption(
            "Paste an Anthropic API key to enable the AI roadmap and the **Ask** tab. It stays in "
            "this browser session only — it is never stored or sent anywhere but Anthropic."
        )
        st.text_input(
            "Anthropic API key",
            type="password",
            key="api_key",
            placeholder="sk-ant-...",
            help="Get one at console.anthropic.com. Explore and Skill-gap work without it.",
        )


def main() -> None:
    st.title("📡 SkillRadar")
    st.caption(
        "Real tech job postings from public ATS feeds (Greenhouse · Lever · Ashby), "
        "aggregated into in-demand skills per role. Read-only — every posting links to its source."
    )

    render_sidebar()

    read_model = get_read_model()
    if read_model is None:
        if SERVE_ONLY:
            st.info("No data available yet — the scheduled pipeline hasn't published a snapshot.")
        else:
            st.info(
                "No data yet — click **🔄 Refresh data** in the sidebar to fetch jobs from all "
                "boards (~1–2 min)."
            )
        st.stop()

    tab_explore, tab_gap, tab_ask = st.tabs(["Explore", "Skill-gap", "Ask"])
    with tab_explore:
        render_explore(read_model)
    with tab_gap:
        render_skill_gap(read_model)
    with tab_ask:
        render_ask(read_model)


def render_explore(read_model: DuckDbServingReadModel) -> None:
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

        # ---- Demand trend over time (M7) ----
        st.subheader("Demand trend over time")
        trends = read_model.trends(role, top_n)
        if trends.empty:
            st.info("No trend data yet for this role.")
        else:
            if trends["snapshot_date"].nunique() < 2:
                st.caption(
                    "Only one daily snapshot so far — the lines fill in as the scheduled "
                    "pipeline accumulates more days."
                )
            trend_chart = (
                alt.Chart(trends)
                .mark_line(point=True)
                .encode(
                    x=alt.X("snapshot_date:T", title="Snapshot date"),
                    y=alt.Y("job_count:Q", title="Postings requiring skill"),
                    color=alt.Color("skill:N", title="Skill"),
                    tooltip=["snapshot_date:T", "skill:N", "job_count:Q"],
                )
                .properties(height=400)
            )
            st.altair_chart(trend_chart, use_container_width=True)

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


def render_skill_gap(read_model: DuckDbServingReadModel) -> None:
    st.header("Skill-gap analysis")
    st.caption(
        "Paste your current skills and pick a target role to see exactly what you're missing — "
        "ranked by how many real postings require it — then generate a learning roadmap."
    )

    roles = read_model.roles_latest()
    if roles.empty:
        st.info("No role-demand data yet — run the pipeline first.")
        return

    c1, c2 = st.columns([3, 1])
    skills_text = c1.text_area(
        "Your skills",
        placeholder="e.g. python, sql, pandas, react, docker",
        height=90,
    )
    role = c2.selectbox("Target role", roles["role"].tolist(), key="gap_role")
    top_n = c2.slider("Compare top", 10, 40, 25, 5, key="gap_topn")

    if not skills_text.strip():
        st.info("Enter your skills above to see your gap.")
        return

    matcher, id_to_name = get_matcher()
    user_skills = {id_to_name[i] for i in matcher.match(skills_text) if i in id_to_name}
    if user_skills:
        st.caption("Recognized skills: " + ", ".join(sorted(user_skills)))
    else:
        st.warning(
            "Couldn't recognize any known skills there — try comma-separated names like "
            "'Python, SQL, Docker'."
        )

    demand_df = read_model.demand(role, top_n)
    if demand_df.empty:
        st.info("No demand data for this role yet.")
        return

    role_total = read_model.role_total(role)
    demanded = [
        DemandedSkill(r["skill"], r["category"], int(r["job_count"]))
        for r in demand_df.to_dict("records")
    ]
    result = compute_skill_gap(role, user_skills, demanded, role_total)

    m1, m2, m3 = st.columns(3)
    m1.metric("Demand coverage", f"{result.coverage:.0%}")
    m2.metric("Skills you have", f"{len(result.have)}/{len(demanded)}")
    m3.metric(f"{role} postings", role_total)

    if result.missing:
        st.subheader("Top skills you're missing")
        missing_df = pd.DataFrame(
            {
                "skill": g.skill,
                "share": g.share,
                "category": g.category,
                "job_count": g.job_count,
            }
            for g in result.missing
        )
        chart = (
            alt.Chart(missing_df)
            .mark_bar()
            .encode(
                x=alt.X(
                    "share:Q",
                    title="% of postings requiring it",
                    axis=alt.Axis(format="%"),
                ),
                y=alt.Y("skill:N", sort="-x", title=None),
                color=alt.Color("category:N", title="Category"),
                tooltip=[
                    "skill",
                    "category",
                    alt.Tooltip("share:Q", format=".0%", title="Share"),
                    "job_count",
                ],
            )
            .properties(height=max(250, 24 * len(missing_df)))
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.success("You already cover every top skill for this role. 🎉")

    # ---- AI learning roadmap (optional enrichment) ----
    st.subheader("AI learning roadmap")
    generator = get_roadmap_generator()
    if not generator.available:
        st.info(
            "Add an **Anthropic API key** in the sidebar to generate a personalized roadmap from "
            "your gap. The ranked gap above works without it."
        )
    elif not result.missing:
        st.caption("No gap to plan — nothing to generate.")
    elif st.button("Generate roadmap", type="primary"):
        with st.spinner("Generating roadmap…"):
            roadmap = generator.generate(role, result.missing)
        if roadmap is None:
            st.warning("Couldn't generate a roadmap right now. The ranked gap above still applies.")
        else:
            st.markdown(f"**{roadmap.summary}**")
            for i, step in enumerate(roadmap.steps, start=1):
                with st.expander(f"{i}. {step.skill}", expanded=i <= 3):
                    st.write(step.why)
                    if step.resources:
                        st.markdown("\n".join(f"- {r}" for r in step.resources))


def _render_tool_calls(tool_calls: list) -> None:
    if tool_calls:
        with st.expander("Data I queried"):
            for tc in tool_calls:
                st.code(f"{tc['name']}({tc['input']})", language="python")


def render_ask(read_model: DuckDbServingReadModel) -> None:
    st.header("Ask the market")
    st.caption(
        "Ask anything about the aggregated postings — answers come from the real data via "
        "structured queries, with the jobs/numbers they're based on."
    )

    # Lightweight: the agent just holds a reference to the read model, so build it per run
    # (no caching) — this always uses the current connection, even after a Refresh. The skill
    # resolver reuses the same matcher as the pipeline, so "ml"/"k8s" map to canonical names.
    matcher, id_to_name = get_matcher()

    def _resolver(query: str) -> list[str]:
        return sorted({id_to_name[i] for i in matcher.match(query) if i in id_to_name})

    agent = MarketChatAgent(
        read_model, model=CONFIG.llm_model, api_key=_api_key(), skill_resolver=_resolver
    )
    if not agent.available:
        st.info(
            "Add an **Anthropic API key** in the sidebar to chat with the market. The Explore and "
            "Skill-gap tabs work without it."
        )
        return

    history = st.session_state.setdefault("ask_history", [])
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"] or "_(no answer)_")
            if msg["role"] == "assistant":
                _render_tool_calls(msg.get("tool_calls", []))

    prompt = st.chat_input("e.g. Which remote companies want Rust?")
    if not prompt:
        return

    history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Querying the market…"):
            result = agent.answer(prompt)
        st.markdown(result.text or "_(no answer)_")
        _render_tool_calls(result.tool_calls)
    history.append({"role": "assistant", "content": result.text, "tool_calls": result.tool_calls})


if __name__ == "__main__":
    main()
