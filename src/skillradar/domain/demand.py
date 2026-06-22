"""Gold aggregation rule — pure. Count, per role, how many postings require each skill.

Port of the .NET ``AggregateSkillDemandAsync``: over the active jobs (deduplicated
cross-source by content hash), a job belongs to a role when its lower-cased title contains
any of that role's patterns; for each role we count the distinct postings that mention each
skill. Reimplemented with plain dict/set bookkeeping so the domain stays free of pandas."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from skillradar.domain.records import ActiveJob, DemandRow, SkillLink
from skillradar.domain.roles import DEFAULT_ROLES


def aggregate_demand(
    active_jobs: Iterable[ActiveJob],
    links: Iterable[SkillLink],
    snapshot_date: date,
) -> list[DemandRow]:
    # Cross-source dedup: keep the first job seen for each content hash.
    seen_hashes: set[str] = set()
    kept: list[ActiveJob] = []
    for job in active_jobs:
        if job.dedup_hash in seen_hashes:
            continue
        seen_hashes.add(job.dedup_hash)
        kept.append(job)

    kept_ids = {job.job_id for job in kept}

    # Distinct skill per job (first category wins), restricted to kept jobs — mirrors the
    # .NET ``drop_duplicates(["job_id", "skill"])`` before counting.
    job_skills: dict[str, dict[str, str | None]] = {}
    for link in links:
        if link.job_id not in kept_ids:
            continue
        job_skills.setdefault(link.job_id, {}).setdefault(link.skill, link.category)

    rows: list[DemandRow] = []
    for role_name, patterns in DEFAULT_ROLES:
        matching_ids = [
            job.job_id for job in kept if any(p in job.title.lower() for p in patterns)
        ]
        if not matching_ids:
            continue

        counts: dict[tuple[str, str | None], int] = {}
        for job_id in matching_ids:
            for skill, category in job_skills.get(job_id, {}).items():
                counts[(skill, category)] = counts.get((skill, category), 0) + 1

        for (skill, category), count in counts.items():
            rows.append(DemandRow(role_name, skill, category, count, snapshot_date))

    return rows
