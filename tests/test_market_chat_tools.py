"""The market-chat tool dispatcher routes to the read model and shapes JSON-serializable results,
and the agent degrades gracefully with no API key. No network, no DuckDB — a fake read model."""

import json

import pandas as pd

from skillradar.infrastructure.ai.market_chat import MarketChatAgent


class FakeReadModel:
    def stats(self):
        return pd.DataFrame(
            [{"active_jobs": 100, "skills_seen": 42, "last_run": "2026-06-23T10:58"}]
        )

    def roles_latest(self):
        return pd.DataFrame({"role": ["Data Engineer", "Backend Engineer"]})

    def distinct_skills(self):
        return ["Python", "Rust", "Machine Learning", "SQL"]

    def role_total(self, role):
        return 50

    def demand(self, role, top_n):
        return pd.DataFrame(
            [
                {"skill": "Spark", "category": "Data", "job_count": 30},
                {"skill": "Airflow", "category": "Data", "job_count": 20},
            ]
        ).head(top_n)

    def job_count(self, f):
        return 7

    def jobs_page(self, f, limit, offset):
        return pd.DataFrame(
            [
                {
                    "company": "Acme",
                    "title": "Data Engineer",
                    "location": "Remote",
                    "is_remote": True,
                    "source": "greenhouse",
                    "apply_url": "https://acme.example/job",
                    "posted_at": None,
                    "skills": "Spark",
                }
            ]
        ).head(limit)

    def companies_hiring(self, skill=None, limit=10):
        return pd.DataFrame(
            [{"company": "Acme", "job_count": 5}, {"company": "Globex", "job_count": 3}]
        ).head(limit)


def _agent() -> MarketChatAgent:
    return MarketChatAgent(FakeReadModel(), model="claude-haiku-4-5", api_key=None)


def test_no_api_key_reports_unavailable():
    agent = _agent()
    assert agent.available is False
    assert agent.answer("anything").available is False


def test_market_overview():
    out = _agent()._dispatch("market_overview", {})
    assert out == {"active_jobs": 100, "skills_observed": 42, "last_refresh": "2026-06-23T10:58"}


def test_list_roles():
    assert _agent()._dispatch("list_roles", {})["roles"] == ["Data Engineer", "Backend Engineer"]


def test_resolve_skill_substring_fallback():
    # No resolver injected → substring over canonical names (case-insensitive).
    assert _agent()._dispatch("resolve_skill", {"query": "RUST"})["matches"] == ["Rust"]
    machine = _agent()._dispatch("resolve_skill", {"query": "machine"})
    assert machine["matches"] == ["Machine Learning"]


def test_resolve_skill_uses_injected_resolver_for_aliases():
    # With the matcher-backed resolver, aliases like "ml" map to the canonical name.
    agent = MarketChatAgent(
        FakeReadModel(),
        model="claude-haiku-4-5",
        api_key=None,
        skill_resolver=lambda q: ["Machine Learning"] if q.lower() == "ml" else [],
    )
    assert agent._dispatch("resolve_skill", {"query": "ml"})["matches"] == ["Machine Learning"]


def test_top_skills_for_role_computes_share():
    out = _agent()._dispatch("top_skills_for_role", {"role": "Data Engineer"})
    assert out["role_postings"] == 50
    assert out["skills"][0] == {
        "skill": "Spark",
        "category": "Data",
        "job_count": 30,
        "share_pct": 60.0,  # 30 / 50
    }


def test_find_jobs_shapes_results():
    out = _agent()._dispatch("find_jobs", {"skill": "Spark", "remote": "remote"})
    assert out["total_matches"] == 7
    assert out["jobs"][0]["company"] == "Acme"
    assert out["jobs"][0]["apply_url"].startswith("https://")


def test_companies_hiring():
    out = _agent()._dispatch("companies_hiring", {"skill": "Rust"})
    assert out["companies"] == [
        {"company": "Acme", "job_count": 5},
        {"company": "Globex", "job_count": 3},
    ]


def test_unknown_tool_returns_error():
    assert "error" in _agent()._dispatch("nope", {})


def test_all_results_are_json_serializable():
    agent = _agent()
    for name, args in [
        ("market_overview", {}),
        ("list_roles", {}),
        ("resolve_skill", {"query": "py"}),
        ("top_skills_for_role", {"role": "Data Engineer"}),
        ("find_jobs", {"skill": "Spark"}),
        ("companies_hiring", {}),
    ]:
        json.dumps(agent._dispatch(name, args))  # must not raise
