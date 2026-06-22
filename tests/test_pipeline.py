"""Silver + Gold pipeline tests (port of GoldAggregationTests + dedup/lifecycle cases)."""

from datetime import UTC, datetime

import pytest

from skillradar.common.db import connect, ensure_schema
from skillradar.common.models import FetchedJob, JobSource
from skillradar.gold.aggregate import aggregate_skill_demand
from skillradar.silver.normalize import upsert_jobs
from skillradar.skills.dictionary import Skill
from skillradar.skills.extract import extract_job_skills

NOW = datetime(2026, 6, 21, tzinfo=UTC)
GH = JobSource.greenhouse
LV = JobSource.lever
GH_ACME = {("greenhouse", "acme")}


@pytest.fixture
def con(tmp_path):
    connection = connect(tmp_path / "test.duckdb")
    ensure_schema(connection)
    yield connection
    connection.close()


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


def test_extracts_skills_and_aggregates_demand_for_matching_role(con):
    fetched = [
        fj(GH, "acme", "1", "Senior Data Engineer", desc="We use Python and k8s daily."),
        fj(GH, "acme", "2", "Data Engineer", desc="Strong Python required."),
        fj(GH, "acme", "3", "Frontend Engineer", desc="Python optional."),
    ]
    upserted, _ = upsert_jobs(con, fetched, GH_ACME, NOW)
    assert len(upserted) == 3

    extract_job_skills(con, upserted, SKILLS)
    # job1 -> Python + Kubernetes(via k8s), job2 -> Python, job3 -> Python = 4 links
    assert con.execute("SELECT count(*) FROM job_skills").fetchone()[0] == 4

    aggregate_skill_demand(con, NOW)
    python = con.execute(
        "SELECT job_count FROM skill_demand WHERE role = 'Data Engineer' AND skill = 'Python'"
    ).fetchone()
    k8s = con.execute(
        "SELECT job_count FROM skill_demand WHERE role = 'Data Engineer' AND skill = 'Kubernetes'"
    ).fetchone()
    assert python[0] == 2  # jobs 1 and 2 (job 3 is Frontend)
    assert k8s[0] == 1


def test_cross_source_duplicate_is_skipped(con):
    # Same company/title/location from two different sources in one run -> one job kept.
    fetched = [
        fj(GH, "acme", "g1", "Engineer", company="Acme", location="NYC"),
        fj(LV, "acme", "l1", "Engineer", company="Acme", location="NYC"),
    ]
    boards = {("greenhouse", "acme"), ("lever", "acme")}
    upserted, _ = upsert_jobs(con, fetched, boards, NOW)
    assert len(upserted) == 1
    assert con.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1


def test_lifecycle_deactivates_vanished_jobs_for_succeeded_board(con):
    upsert_jobs(con, [fj(GH, "acme", "1", "Engineer")], GH_ACME, NOW)
    assert con.execute("SELECT count(*) FROM jobs WHERE is_active").fetchone()[0] == 1

    # Board fetched successfully but returned nothing -> the job is deactivated.
    _, deactivated = upsert_jobs(con, [], GH_ACME, NOW)
    assert deactivated == 1
    assert con.execute("SELECT count(*) FROM jobs WHERE is_active").fetchone()[0] == 0


def test_failed_board_does_not_deactivate_its_jobs(con):
    upsert_jobs(con, [fj(GH, "acme", "1", "Engineer")], GH_ACME, NOW)
    # Empty fetch AND the board is not in succeeded set (it failed) -> leave untouched.
    _, deactivated = upsert_jobs(con, [], set(), NOW)
    assert deactivated == 0
    assert con.execute("SELECT count(*) FROM jobs WHERE is_active").fetchone()[0] == 1
