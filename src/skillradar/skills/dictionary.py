"""Load the canonical skill dictionary (data/skills.seed.json) and build a matcher."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .guards import DEFAULT_GUARDS
from .matcher import SkillMatcher, SkillTerms


@dataclass(frozen=True)
class Skill:
    skill_id: int
    name: str
    category: str
    aliases: tuple[str, ...]


def load_skills(path: str | Path) -> list[Skill]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    skills: list[Skill] = []
    for i, item in enumerate(data.get("skills", []), start=1):
        skills.append(
            Skill(
                skill_id=i,
                name=item["name"],
                category=item.get("category", ""),
                aliases=tuple(item.get("aliases", [])),
            )
        )
    return skills


def build_matcher(skills: list[Skill]) -> SkillMatcher:
    """The canonical name is always a matchable term alongside every alias."""
    terms = [SkillTerms(s.skill_id, s.name, (s.name, *s.aliases)) for s in skills]
    return SkillMatcher(terms, DEFAULT_GUARDS)
