"""Runtime configuration. Paths default to the project's ``data/`` folder and can be
overridden with ``SKILLRADAR_*`` environment variables (handy for CI / Streamlit Cloud)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# config.py -> infrastructure -> skillradar -> src -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name) or default


@dataclass(frozen=True)
class Config:
    sources_path: Path = _env_path("SKILLRADAR_SOURCES", DATA_DIR / "sources.json")
    skills_path: Path = _env_path("SKILLRADAR_SKILLS", DATA_DIR / "skills.seed.json")
    duckdb_path: Path = _env_path("SKILLRADAR_DUCKDB", DATA_DIR / "skillradar.duckdb")
    bronze_dir: Path = _env_path("SKILLRADAR_BRONZE", DATA_DIR / "bronze")
    # Polite delay between board calls so we never hammer a source.
    delay_between_boards_ms: int = _env_int("SKILLRADAR_DELAY_MS", 500)
    # Optional LLM learning-roadmap enrichment (needs ANTHROPIC_API_KEY at runtime).
    llm_model: str = _env_str("SKILLRADAR_LLM_MODEL", "claude-haiku-4-5")
    roadmap_cache_dir: Path = _env_path("SKILLRADAR_ROADMAP_CACHE", DATA_DIR / "roadmap_cache")
    # MotherDuck database name used in production (when MOTHERDUCK_TOKEN is set). See data_target.
    motherduck_database: str = _env_str("SKILLRADAR_MOTHERDUCK_DB", "skillradar")


def data_target(config: Config) -> str:
    """The single source of truth for *where the warehouse lives*.

    Returns a MotherDuck target (``md:<db>``) when ``MOTHERDUCK_TOKEN`` is set — the production
    data layer, a cloud DuckDB — otherwise the local DuckDB file path for development. The token
    itself is read from the environment by DuckDB's MotherDuck extension at connect time."""
    if os.environ.get("MOTHERDUCK_TOKEN"):
        return f"md:{config.motherduck_database}"
    return str(config.duckdb_path)


def load_config() -> Config:
    return Config()
