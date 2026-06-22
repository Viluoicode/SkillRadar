"""Extract skills from job text into the ``job_skills`` table.

Mirrors the .NET extraction: a job's matched skills come from its title + description,
links are rebuilt for the affected jobs (incremental per-run, or a full re-extract)."""

from __future__ import annotations

import duckdb
import pandas as pd

from ..common.logging import get_logger
from .dictionary import Skill, build_matcher

logger = get_logger(__name__)


def extract_job_skills(
    con: duckdb.DuckDBPyConnection,
    job_ids: list[str],
    skills: list[Skill],
    *,
    replace_all: bool = False,
) -> int:
    """Rebuild ``job_skills`` for the given jobs (or all jobs when ``replace_all``).

    Returns the number of jobs processed."""
    matcher = build_matcher(skills)
    id_to_skill = {s.skill_id: s for s in skills}

    if replace_all:
        rows = con.execute("SELECT job_id, title, description FROM jobs").df()
        con.execute("DELETE FROM job_skills")
    else:
        if not job_ids:
            return 0
        ids_df = pd.DataFrame({"job_id": list(dict.fromkeys(job_ids))})
        con.register("ids_df", ids_df)
        try:
            rows = con.execute(
                "SELECT job_id, title, description FROM jobs "
                "WHERE job_id IN (SELECT job_id FROM ids_df)"
            ).df()
            con.execute("DELETE FROM job_skills WHERE job_id IN (SELECT job_id FROM ids_df)")
        finally:
            con.unregister("ids_df")

    links: list[tuple[str, str, str]] = []
    for row in rows.itertuples(index=False):
        text = f"{row.title}\n{row.description}"
        for skill_id in matcher.match(text):
            skill = id_to_skill[skill_id]
            links.append((row.job_id, skill.name, skill.category))

    if links:
        links_df = pd.DataFrame(links, columns=["job_id", "skill", "category"])
        con.register("links_df", links_df)
        try:
            con.execute("INSERT INTO job_skills SELECT * FROM links_df")
        finally:
            con.unregister("links_df")

    logger.info("Skills: extracted %d links across %d jobs", len(links), len(rows))
    return len(rows)
