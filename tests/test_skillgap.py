"""Unit tests for the pure skill-gap computation (no I/O)."""

from skillradar.domain.skillgap import DemandedSkill, compute_skill_gap


def _demand() -> list[DemandedSkill]:
    return [
        DemandedSkill("Python", "Language", 80),
        DemandedSkill("SQL", "Language", 60),
        DemandedSkill("Spark", "Data", 40),
        DemandedSkill("Airflow", "Data", 20),
    ]


def test_splits_have_and_missing_case_insensitive():
    result = compute_skill_gap("Data Engineer", ["python", "SQL"], _demand(), role_total=100)
    assert {g.skill for g in result.have} == {"Python", "SQL"}
    assert {g.skill for g in result.missing} == {"Spark", "Airflow"}


def test_share_is_job_count_over_role_total():
    result = compute_skill_gap("Data Engineer", [], _demand(), role_total=100)
    shares = {g.skill: g.share for g in result.missing}
    assert shares["Python"] == 0.8
    assert shares["Airflow"] == 0.2


def test_missing_sorted_by_demand_desc():
    result = compute_skill_gap("Data Engineer", [], _demand(), role_total=100)
    counts = [g.job_count for g in result.missing]
    assert counts == sorted(counts, reverse=True)
    assert result.missing[0].skill == "Python"


def test_coverage_is_demand_weighted():
    # Having Python (80) + SQL (60) of total demand 200 → 140/200 = 0.7.
    result = compute_skill_gap("Data Engineer", ["Python", "SQL"], _demand(), role_total=100)
    assert result.coverage == 0.7


def test_full_coverage_when_user_has_everything():
    result = compute_skill_gap(
        "Data Engineer", ["Python", "SQL", "Spark", "Airflow"], _demand(), role_total=100
    )
    assert result.missing == ()
    assert result.coverage == 1.0


def test_no_demand_yields_zero_coverage_without_error():
    result = compute_skill_gap("Data Engineer", ["Python"], [], role_total=0)
    assert result.coverage == 0.0
    assert result.have == () and result.missing == ()


def test_role_total_zero_gives_zero_share_no_div_by_zero():
    result = compute_skill_gap("Data Engineer", [], _demand(), role_total=0)
    assert all(g.share == 0.0 for g in result.missing)


def test_user_skill_outside_demand_is_ignored():
    result = compute_skill_gap("Data Engineer", ["Rust"], _demand(), role_total=100)
    assert result.have == ()
    assert len(result.missing) == 4
    assert result.coverage == 0.0
