"""data_target() is the single source of truth for where the warehouse lives: a MotherDuck cloud
database in production (MOTHERDUCK_TOKEN set) or the local DuckDB file in dev. No network."""

from pathlib import Path

from skillradar.infrastructure.config import Config, data_target


def test_local_file_when_no_token(monkeypatch, tmp_path):
    monkeypatch.delenv("MOTHERDUCK_TOKEN", raising=False)
    config = Config(duckdb_path=tmp_path / "skillradar.duckdb")
    assert data_target(config) == str(tmp_path / "skillradar.duckdb")
    assert not data_target(config).startswith("md:")


def test_motherduck_when_token_set(monkeypatch):
    monkeypatch.setenv("MOTHERDUCK_TOKEN", "fake-token")
    config = Config(motherduck_database="skillradar")
    assert data_target(config) == "md:skillradar"


def test_motherduck_database_name_is_honored(monkeypatch):
    monkeypatch.setenv("MOTHERDUCK_TOKEN", "fake-token")
    config = Config(motherduck_database="skillradar_prod")
    assert data_target(config) == "md:skillradar_prod"


def test_token_takes_precedence_over_local_path(monkeypatch, tmp_path):
    # Even with a local file configured, a token routes to MotherDuck (production wins).
    monkeypatch.setenv("MOTHERDUCK_TOKEN", "fake-token")
    config = Config(duckdb_path=tmp_path / "local.duckdb", motherduck_database="skillradar")
    assert data_target(config) == "md:skillradar"
    assert isinstance(config.duckdb_path, Path)  # local path still available for tooling
