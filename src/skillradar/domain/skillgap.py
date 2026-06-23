"""Skill-gap analysis — pure domain logic.

Given a user's current skills and a role's in-demand skills (with how many postings require
each), compute what the user already covers and what they're missing, ranked by real demand.

Also defines the LLM-roadmap output contract (:class:`Roadmap`) returned by the optional
``LearningRoadmapGenerator`` port. It lives here, in the domain, so the port and its
infrastructure adapter both depend inward on a pure type (pydantic is allowed in the domain;
duckdb/httpx/anthropic are not)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class DemandedSkill:
    """One in-demand skill for a role: how many postings require it."""

    skill: str
    category: str | None
    job_count: int


@dataclass(frozen=True)
class GapSkill:
    """A demanded skill tagged with the share of the role's postings that require it."""

    skill: str
    category: str | None
    job_count: int
    share: float  # job_count / role_total, in [0, 1]


@dataclass(frozen=True)
class SkillGapResult:
    """The user's standing against a role's demand."""

    role: str
    role_total: int
    have: tuple[GapSkill, ...]  # demanded skills the user already has, share desc
    missing: tuple[GapSkill, ...]  # demanded skills the user lacks, share desc
    coverage: float  # demand-weighted share the user already covers, in [0, 1]


def _norm(name: str) -> str:
    return name.strip().lower()


def compute_skill_gap(
    role: str,
    user_skills: Iterable[str],
    demanded: Iterable[DemandedSkill],
    role_total: int,
) -> SkillGapResult:
    """Split a role's demanded skills into what the user has vs is missing.

    ``share`` = postings requiring the skill / ``role_total`` (the count of distinct postings
    for the role). ``coverage`` weights each skill by ``job_count``, so covering high-demand
    skills counts for more than niche ones. Matching is case-insensitive by canonical name;
    user skills outside the demanded set don't affect the result.
    """
    have_names = {_norm(s) for s in user_skills}
    demanded_list = list(demanded)
    total_weight = sum(d.job_count for d in demanded_list)

    have: list[GapSkill] = []
    missing: list[GapSkill] = []
    covered_weight = 0
    for d in demanded_list:
        share = d.job_count / role_total if role_total > 0 else 0.0
        gap_skill = GapSkill(d.skill, d.category, d.job_count, share)
        if _norm(d.skill) in have_names:
            have.append(gap_skill)
            covered_weight += d.job_count
        else:
            missing.append(gap_skill)

    have.sort(key=lambda g: (-g.job_count, g.skill))
    missing.sort(key=lambda g: (-g.job_count, g.skill))
    coverage = covered_weight / total_weight if total_weight > 0 else 0.0

    return SkillGapResult(role, role_total, tuple(have), tuple(missing), coverage)


# --- LLM roadmap output contract (validated structure the generator must return) ----------


class RoadmapStep(BaseModel):
    """One learning step, grounded in the gap it addresses."""

    skill: str
    why: str  # rationale that should cite the demand (e.g. "in 64% of Data Engineer postings")
    resources: list[str] = Field(default_factory=list)


class Roadmap(BaseModel):
    """An ordered learning plan for the missing skills of a role."""

    role: str
    summary: str
    steps: list[RoadmapStep]
