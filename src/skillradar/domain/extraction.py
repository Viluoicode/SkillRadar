"""Skill extraction rule — pure. Turn job text into (job → skill) links via the matcher."""

from __future__ import annotations

from collections.abc import Iterable

from skillradar.domain.records import JobText, SkillLink
from skillradar.domain.skills.dictionary import Skill
from skillradar.domain.skills.matcher import SkillMatcher


def extract_links(
    texts: Iterable[JobText], matcher: SkillMatcher, skills: list[Skill]
) -> list[SkillLink]:
    """For each posting, match its title + description and emit one link per distinct skill."""
    id_to_skill = {s.skill_id: s for s in skills}
    links: list[SkillLink] = []
    for t in texts:
        blob = f"{t.title}\n{t.description}"
        for skill_id in matcher.match(blob):
            skill = id_to_skill[skill_id]
            links.append(SkillLink(t.job_id, skill.name, skill.category))
    return links
