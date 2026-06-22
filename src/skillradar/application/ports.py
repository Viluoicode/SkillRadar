"""Ports — the abstract boundaries the application depends on.

Each protocol is a seam the infrastructure layer implements (DuckDB repositories, httpx
connectors, JSON catalogs, Parquet bronze store). Because the use-cases program against
these instead of concrete tech, the pipeline can run against fakes in tests and the storage
or HTTP stack can change without touching business logic."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Protocol

from skillradar.application.dto import BoardConfig, FetchOutcome, RunRecord
from skillradar.domain.models import FetchedJob, JobSource
from skillradar.domain.records import ActiveJob, DemandRow, JobRecord, JobText, SkillLink
from skillradar.domain.skills.dictionary import Skill


class JobSourceConnector(Protocol):
    """A connector to one ATS platform. ``fetch`` returns all live postings for a single
    board token in the canonical :class:`FetchedJob` shape, surfacing transport failures as
    exceptions so the pipeline can isolate a failing board."""

    source: JobSource

    def fetch(self, board_token: str) -> list[FetchedJob]: ...


class BoardFetcher(Protocol):
    """Fetch every curated board with per-board isolation + polite delay (Bronze fetch)."""

    def fetch_all(self, boards: Sequence[BoardConfig]) -> FetchOutcome: ...


class BoardCatalog(Protocol):
    """Load the curated board list (data/sources.json)."""

    def load(self) -> list[BoardConfig]: ...


class SkillCatalog(Protocol):
    """Load the canonical skill dictionary (data/skills.seed.json)."""

    def load(self) -> list[Skill]: ...


class BronzeStore(Protocol):
    """Land raw payloads exactly as fetched (replayable)."""

    def land(self, fetched: Sequence[FetchedJob], run_id: str, fetched_at: datetime) -> None: ...


class JobRepository(Protocol):
    """Persistence for the Silver ``jobs`` table."""

    def load_all(self) -> list[JobRecord]: ...
    def save_all(self, jobs: Sequence[JobRecord]) -> None: ...
    def active_jobs(self) -> list[ActiveJob]: ...
    def texts_for(self, job_ids: Sequence[str]) -> list[JobText]: ...
    def all_texts(self) -> list[JobText]: ...


class SkillLinkRepository(Protocol):
    """Persistence for the Silver ``job_skills`` table."""

    def all_links(self) -> list[SkillLink]: ...
    def replace_for(self, job_ids: Sequence[str], links: Sequence[SkillLink]) -> None: ...
    def replace_all(self, links: Sequence[SkillLink]) -> None: ...


class DemandRepository(Protocol):
    """Persistence for the Gold ``skill_demand`` + ``skill_trends`` tables."""

    def replace_snapshot(self, snapshot_date: date, rows: Sequence[DemandRow]) -> None: ...


class RunRepository(Protocol):
    """Persistence for the meta ``ingestion_runs`` table."""

    def record(self, run: RunRecord) -> None: ...
