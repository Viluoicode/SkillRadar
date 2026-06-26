"""Parity guarantee for the dbt cutover: the dbt Gold mart ``skill_demand`` must reproduce the
Python ``domain.demand.aggregate_demand`` exactly, row for row.

This is the safety net that lets dbt own Silver→Gold while the Python aggregation stays as the
fallback. It shells out to a real ``dbt build`` against a temp DuckDB seeded with a hand-built
Silver dataset, then compares the dbt output to the pure-Python aggregation on the same inputs.

Skipped unless dbt is reachable: ``dbt`` on PATH, or ``SKILLRADAR_DBT_EXE`` pointing at a dbt
executable (handy locally, where dbt lives in an isolated 3.12 env)."""

from __future__ import annotations

import os
import shutil
from datetime import UTC, date, datetime

import pytest

from skillradar.domain.demand import aggregate_demand
from skillradar.domain.records import JobRecord, SkillLink
from skillradar.infrastructure.db.repositories import (
    DuckDbJobRepository,
    DuckDbSkillLinkRepository,
)
from skillradar.infrastructure.db.warehouse import connect, ensure_schema
from skillradar.infrastructure.dbt.runner import run_dbt_gold

SNAP = date(2026, 6, 26)
T0 = datetime(2026, 6, 1, tzinfo=UTC)


def _dbt_exe() -> str | None:
    return os.environ.get("SKILLRADAR_DBT_EXE") or shutil.which("dbt")


def _job(job_id, source, sid, company, title, dedup_hash, *, active=True):
    return JobRecord(
        job_id=job_id, source=source, source_job_id=sid, board_token=company.lower(),
        company=company, title=title, location="Remote", is_remote=True,
        description="", apply_url="https://example.com/apply", posted_at=T0,
        dedup_hash=dedup_hash, first_seen_at=T0, last_seen_at=T0, is_active=active,
    )


@pytest.mark.dbt
@pytest.mark.skipif(_dbt_exe() is None, reason="dbt not found (set SKILLRADAR_DBT_EXE to run)")
def test_dbt_skill_demand_matches_python(tmp_path):
    db = tmp_path / "parity.duckdb"
    con = connect(db)
    ensure_schema(con)
    jobs = DuckDbJobRepository(con)
    links = DuckDbSkillLinkRepository(con)

    # HASH_D1 is shared by two near-duplicate postings with DIFFERENT skills (dedup_hash ignores
    # the description). "d-j1b" is saved first so DB scan order != min(job_id); only a deterministic
    # min(job_id) dedup — which both dbt and the (fixed) Python rule use — makes them agree.
    jobs.save_all([
        _job("d-j1b", "lever",      "l1", "Acme",    "Senior Data Engineer", "HASH_D1"),
        _job("d-j1",  "greenhouse", "g1", "Acme",    "Senior Data Engineer", "HASH_D1"),
        _job("d-j2",  "greenhouse", "g2", "Acme",    "Data Engineer",        "HASH_D2"),
        _job("b-j3",  "greenhouse", "g3", "Globex",  "Backend Engineer",     "HASH_B1"),
        _job("b-j3b", "lever",      "l3", "Globex",  "Backend Engineer",     "HASH_B1"),  # dup
        _job("f-j4",  "greenhouse", "g4", "Initech", "Frontend Engineer",    "HASH_F1"),
        _job("x-j5",  "greenhouse", "g5", "Acme",    "Data Engineer", "HASH_D5", active=False),
    ])
    links.replace_all([
        SkillLink("d-j1",  "Python", "Language"),
        SkillLink("d-j1",  "Airflow", "Data"),
        SkillLink("d-j1b", "Python", "Language"),
        SkillLink("d-j1b", "Spark", "Data"),          # the near-dup carries a different skill
        SkillLink("d-j2",  "Python", "Language"),
        SkillLink("b-j3",  "Go", "Language"),
        SkillLink("b-j3",  "Kubernetes", "DevOps"),
        SkillLink("b-j3b", "Go", "Language"),
        SkillLink("b-j3b", "Kubernetes", "DevOps"),
        SkillLink("f-j4",  "TypeScript", "Language"),
        SkillLink("f-j4",  "React", "Frontend"),
        SkillLink("x-j5",  "Python", "Language"),      # inactive job — must be excluded
    ])

    expected = {
        (r.role, r.skill, r.category, r.job_count)
        for r in aggregate_demand(jobs.active_jobs(), links.all_links(), SNAP)
    }
    con.close()  # release the single-writer lock before dbt opens the file

    run_dbt_gold(db, SNAP, dbt_executable=_dbt_exe())

    rcon = connect(db, read_only=True)
    got = {
        tuple(row)
        for row in rcon.execute(
            "SELECT role, skill, category, job_count FROM skill_demand WHERE snapshot_date = ?",
            [SNAP],
        ).fetchall()
    }
    rcon.close()

    assert expected, "fixture produced no demand rows — the test would be vacuous"
    assert got == expected
