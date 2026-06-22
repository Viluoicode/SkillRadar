"""The pipeline use-cases run against in-memory fakes — no DuckDB, no I/O.

This is the payoff of the ports/Clean-Architecture split: because the services depend on
repository protocols rather than a connection, the whole Silver→Gold flow is exercised with
trivial in-memory doubles. If this passes, the business rules are provably storage-agnostic.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime

from skillradar.application.services.gold import aggregate_skill_demand
from skillradar.application.services.silver import upsert_jobs
from skillradar.application.services.skills import extract_job_skills
from skillradar.domain.models import FetchedJob, JobSource
from skillradar.domain.records import ActiveJob, DemandRow, JobRecord, JobText, SkillLink
from skillradar.domain.skills.dictionary import Skill

NOW = datetime(2026, 6, 21, tzinfo=UTC)
GH = JobSource.greenhouse


class FakeJobRepository:
    def __init__(self) -> None:
        self._jobs: list[JobRecord] = []

    def load_all(self) -> list[JobRecord]:
        return [replace(j) for j in self._jobs]

    def save_all(self, jobs: Sequence[JobRecord]) -> None:
        self._jobs = [replace(j) for j in jobs]

    def active_jobs(self) -> list[ActiveJob]:
        return [ActiveJob(j.job_id, j.title, j.dedup_hash) for j in self._jobs if j.is_active]

    def texts_for(self, job_ids: Sequence[str]) -> list[JobText]:
        wanted = set(job_ids)
        return [JobText(j.job_id, j.title, j.description) for j in self._jobs if j.job_id in wanted]

    def all_texts(self) -> list[JobText]:
        return [JobText(j.job_id, j.title, j.description) for j in self._jobs]


class FakeSkillLinkRepository:
    def __init__(self) -> None:
        self.links: list[SkillLink] = []

    def all_links(self) -> list[SkillLink]:
        return list(self.links)

    def replace_for(self, job_ids: Sequence[str], links: Sequence[SkillLink]) -> None:
        drop = set(job_ids)
        self.links = [link for link in self.links if link.job_id not in drop] + list(links)

    def replace_all(self, links: Sequence[SkillLink]) -> None:
        self.links = list(links)


class FakeDemandRepository:
    def __init__(self) -> None:
        self.snapshots: dict[date, list[DemandRow]] = {}

    def replace_snapshot(self, snapshot_date: date, rows: Sequence[DemandRow]) -> None:
        self.snapshots[snapshot_date] = list(rows)


def _fj(sid, title, desc):
    return FetchedJob(
        source=GH, board_token="acme", source_job_id=sid, raw_json="{}",
        company="acme", title=title, description=desc,
    )


def test_full_silver_to_gold_flow_against_fakes():
    jobs = FakeJobRepository()
    links = FakeSkillLinkRepository()
    demand = FakeDemandRepository()
    skills = [Skill(1, "Python", "Language", ()), Skill(2, "Kubernetes", "DevOps", ("k8s",))]

    fetched = [
        _fj("1", "Senior Data Engineer", "We use Python and k8s daily."),
        _fj("2", "Data Engineer", "Strong Python required."),
        _fj("3", "Frontend Engineer", "Python optional."),
    ]

    upserted, deactivated = upsert_jobs(jobs, fetched, {("greenhouse", "acme")}, NOW)
    assert len(upserted) == 3 and deactivated == 0

    processed = extract_job_skills(jobs, links, upserted, skills)
    assert processed == 3
    assert len(links.all_links()) == 4  # 3x Python + 1x Kubernetes

    rows = aggregate_skill_demand(jobs, links, demand, NOW)
    assert rows > 0
    de = {
        (r.skill): r.job_count
        for r in demand.snapshots[NOW.date()]
        if r.role == "Data Engineer"
    }
    assert de["Python"] == 2  # jobs 1 and 2 (job 3 is Frontend)
    assert de["Kubernetes"] == 1
