"""Exception hierarchy for SkillRadar. Layers raise these instead of bare ``Exception`` so
callers (and the per-board isolation loop) can distinguish failure kinds."""

from __future__ import annotations


class SkillRadarError(Exception):
    """Base class for all SkillRadar errors."""


class ConfigError(SkillRadarError):
    """Invalid or missing runtime configuration."""


class CatalogError(SkillRadarError):
    """A data catalog (sources.json / skills.seed.json) could not be loaded or parsed."""


class BoardFetchError(SkillRadarError):
    """A single ATS board failed to fetch. Isolated by the ingestion loop, never fatal."""


class RepositoryError(SkillRadarError):
    """A persistence operation failed."""
