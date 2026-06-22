"""Silver + Gold pipeline tests (port of GoldAggregationTests + dedup/lifecycle cases).

These are integration tests: the application services are driven through the real DuckDB
repositories, and results are asserted by querying the warehouse directly."""

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from skillradar.application.services.gold import aggregate_skill_demand
from skillradar.application.services.silver import upsert_jobs
from skillradar.application.services.skills import extract_job_skills
from skillradar.domain.models import FetchedJob, JobSource
from skillradar.domain.skills.dictionary import Skill
from skillradar.infrastructure.db.repositories import (
    DuckDbDemandRepository,
    DuckDbJobRepository,
    DuckDbServingReadModel,
    DuckDbSkillLinkRepository,
)
from skillradar.infrastructure.db.warehouse import connect, ensure_schema

NOW = datetime(2026, 6, 21, tzinfo=UTC)
GH = JobSource.greenhouse
LV = JobSource.lever
GH_ACME = {("greenhouse", "acme")}


@dataclass
class Repos:
    con: object
    jobs: DuckDbJobRepository
    links: DuckDbSkillLinkRepository
    demand: DuckDbDemandRepository


@pytest.fixture
def repos(tmp_path):
    con = connect(tmp_path / "test.duckdb")
    ensure_schema(con)
    yield Repos(
        con=con,
        jobs=DuckDbJobRepository(con),
        links=DuckDbSkillLinkRepository(con),
        demand=DuckDbDemandRepository(con),
    )
    con.close()


def fj(source, token, sid, title, *, desc="", company=None, location=None, remote=False):
    return FetchedJob(
        source=source,
        board_token=token,
        source_job_id=sid,
        raw_json="{}",
        company=company or token,
        title=title,
        location=location,
        remote=remote,
        description=desc,
    )


SKILLS = [
    Skill(1, "Python", "Language", ()),
    Skill(2, "Kubernetes", "DevOps", ("k8s",)),
]


def test_extracts_skills_and_aggregates_demand_for_matching_role(repos):
    fetched = [
        fj(GH, "acme", "1", "Senior Data Engineer", desc="We use Python and k8s daily."),
        fj(GH, "acme", "2", "Data Engineer", desc="Strong Python required."),
        fj(GH, "acme", "3", "Frontend Engineer", desc="Python optional."),
    ]
    upserted, _ = upsert_jobs(repos.jobs, fetched, GH_ACME, NOW)
    assert len(upserted) == 3

    extract_job_skills(repos.jobs, repos.links, upserted, SKILLS)
    # job1 -> Python + Kubernetes(via k8s), job2 -> Python, job3 -> Python = 4 links
    assert repos.con.execute("SELECT count(*) FROM job_skills").fetchone()[0] == 4

    aggregate_skill_demand(repos.jobs, repos.links, repos.demand, NOW)
    python = repos.con.execute(
        "SELECT job_count FROM skill_demand WHERE role = 'Data Engineer' AND skill = 'Python'"
    ).fetchone()
    k8s = repos.con.execute(
        "SELECT job_count FROM skill_demand WHERE role = 'Data Engineer' AND skill = 'Kubernetes'"
    ).fetchone()
    assert python[0] == 2  # jobs 1 and 2 (job 3 is Frontend)
    assert k8s[0] == 1


def test_serving_read_model_trends_accumulate_across_snapshots(repos):
    fetched = [
        fj(GH, "acme", "1", "Senior Data Engineer", desc="We use Python and k8s daily."),
        fj(GH, "acme", "2", "Data Engineer", desc="Strong Python required."),
    ]
    upserted, _ = upsert_jobs(repos.jobs, fetched, GH_ACME, NOW)
    extract_job_skills(repos.jobs, repos.links, upserted, SKILLS)

    # Two daily snapshots accumulate in skill_trends (the demand table holds only the latest).
    day1 = datetime(2026, 6, 20, tzinfo=UTC)
    day2 = datetime(2026, 6, 21, tzinfo=UTC)
    aggregate_skill_demand(repos.jobs, repos.links, repos.demand, day1)
    aggregate_skill_demand(repos.jobs, repos.links, repos.demand, day2)

    trends = DuckDbServingReadModel(repos.con).trends("Data Engineer", top_n=5)
    python_points = trends[trends["skill"] == "Python"]
    assert len(python_points) == 2  # one point per snapshot
    assert set(python_points["job_count"]) == {2}
    assert trends["snapshot_date"].nunique() == 2


def test_cross_source_duplicate_is_skipped(repos):
    # Same company/title/location from two different sources in one run -> one job kept.
    fetched = [
        fj(GH, "acme", "g1", "Engineer", company="Acme", location="NYC"),
        fj(LV, "acme", "l1", "Engineer", company="Acme", location="NYC"),
    ]
    boards = {("greenhouse", "acme"), ("lever", "acme")}
    upserted, _ = upsert_jobs(repos.jobs, fetched, boards, NOW)
    assert len(upserted) == 1
    assert repos.con.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1


def test_lifecycle_deactivates_vanished_jobs_for_succeeded_board(repos):
    upsert_jobs(repos.jobs, [fj(GH, "acme", "1", "Engineer")], GH_ACME, NOW)
    assert repos.con.execute("SELECT count(*) FROM jobs WHERE is_active").fetchone()[0] == 1

    # Board fetched successfully but returned nothing -> the job is deactivated.
    _, deactivated = upsert_jobs(repos.jobs, [], GH_ACME, NOW)
    assert deactivated == 1
    assert repos.con.execute("SELECT count(*) FROM jobs WHERE is_active").fetchone()[0] == 0


def test_failed_board_does_not_deactivate_its_jobs(repos):
    upsert_jobs(repos.jobs, [fj(GH, "acme", "1", "Engineer")], GH_ACME, NOW)
    # Empty fetch AND the board is not in succeeded set (it failed) -> leave untouched.
    _, deactivated = upsert_jobs(repos.jobs, [], set(), NOW)
    assert deactivated == 0
    assert repos.con.execute("SELECT count(*) FROM jobs WHERE is_active").fetchone()[0] == 1
