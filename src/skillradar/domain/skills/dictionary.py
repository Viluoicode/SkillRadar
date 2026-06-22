"""The canonical skill dictionary and how to build a matcher from it.

Loading the dictionary from disk is an I/O concern and lives in the infrastructure layer
(:mod:`skillradar.infrastructure.skills.seed_loader`); this module stays pure so the
matcher can be built and tested without touching the filesystem."""

from __future__ import annotations

from dataclasses import dataclass

from skillradar.domain.skills.guards import DEFAULT_GUARDS
from skillradar.domain.skills.matcher import SkillMatcher, SkillTerms


@dataclass(frozen=True)
class Skill:
    skill_id: int
    name: str
    category: str
    aliases: tuple[str, ...]


def build_matcher(skills: list[Skill]) -> SkillMatcher:
    """The canonical name is always a matchable term alongside every alias."""
    terms = [SkillTerms(s.skill_id, s.name, (s.name, *s.aliases)) for s in skills]
    return SkillMatcher(terms, DEFAULT_GUARDS)
