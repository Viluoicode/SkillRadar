"""Skill-extraction use-case — match job text and rebuild the (job → skill) links."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from skillradar.application.ports import JobRepository, SkillLinkRepository
from skillradar.domain.extraction import extract_links
from skillradar.domain.skills.dictionary import Skill, build_matcher

logger = logging.getLogger(__name__)


def extract_job_skills(
    job_repo: JobRepository,
    link_repo: SkillLinkRepository,
    job_ids: Sequence[str],
    skills: list[Skill],
    *,
    replace_all: bool = False,
) -> int:
    """Rebuild ``job_skills`` for the given jobs (or all jobs when ``replace_all``).

    Returns the number of jobs processed."""
    matcher = build_matcher(skills)

    if replace_all:
        texts = job_repo.all_texts()
        links = extract_links(texts, matcher, skills)
        link_repo.replace_all(links)
    else:
        ids = list(dict.fromkeys(job_ids))
        if not ids:
            return 0
        texts = job_repo.texts_for(ids)
        links = extract_links(texts, matcher, skills)
        link_repo.replace_for(ids, links)

    logger.info("Skills: extracted %d links across %d jobs", len(links), len(texts))
    return len(texts)
