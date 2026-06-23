"""The roadmap generator degrades gracefully (no key → None) and serves cache without a network
call. These tests never hit the Anthropic API and don't require the ``anthropic`` package."""

from skillradar.domain.skillgap import GapSkill, Roadmap, RoadmapStep
from skillradar.infrastructure.ai.anthropic_roadmap import AnthropicRoadmapGenerator

_MISSING = [GapSkill("Spark", "Data", 40, 0.4), GapSkill("Airflow", "Data", 20, 0.2)]


def test_no_api_key_returns_none(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    gen = AnthropicRoadmapGenerator(model="claude-haiku-4-5", cache_dir=tmp_path, api_key=None)
    assert gen.available is False
    assert gen.generate("Data Engineer", _MISSING) is None


def test_empty_missing_returns_none(tmp_path):
    gen = AnthropicRoadmapGenerator(model="claude-haiku-4-5", cache_dir=tmp_path, api_key="k")
    assert gen.generate("Data Engineer", []) is None


def test_cache_hit_avoids_api_call(tmp_path):
    gen = AnthropicRoadmapGenerator(model="claude-haiku-4-5", cache_dir=tmp_path, api_key="k")
    cached = Roadmap(
        role="Data Engineer",
        summary="cached",
        steps=[RoadmapStep(skill="Spark", why="40% of postings", resources=["docs"])],
    )
    # Pre-seed the cache for this (model, role, skills); generate() must return it, no network.
    path = gen._cache_path("Data Engineer", _MISSING)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cached.model_dump_json(), encoding="utf-8")

    result = gen.generate("Data Engineer", _MISSING)
    assert result is not None
    assert result.summary == "cached"
    assert result.steps[0].skill == "Spark"
