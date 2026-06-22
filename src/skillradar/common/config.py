"""Runtime configuration. Paths default to the project's ``data/`` folder and can be
overridden with ``SKILLRADAR_*`` environment variables (handy for CI / Streamlit Cloud)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# config.py -> common -> skillradar -> src -> python (project root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Config:
    sources_path: Path = _env_path("SKILLRADAR_SOURCES", DATA_DIR / "sources.json")
    skills_path: Path = _env_path("SKILLRADAR_SKILLS", DATA_DIR / "skills.seed.json")
    duckdb_path: Path = _env_path("SKILLRADAR_DUCKDB", DATA_DIR / "skillradar.duckdb")
    bronze_dir: Path = _env_path("SKILLRADAR_BRONZE", DATA_DIR / "bronze")
    # Polite delay between board calls so we never hammer a source.
    delay_between_boards_ms: int = _env_int("SKILLRADAR_DELAY_MS", 500)


def load_config() -> Config:
    return Config()
