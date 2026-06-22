"""Data-transfer objects passed between the ingestion ports and the pipeline use-case."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from skillradar.domain.models import FetchedJob, JobSource


@dataclass(frozen=True)
class BoardConfig:
    """One curated company board to ingest (from data/sources.json)."""

    source: JobSource
    token: str
    company: str | None = None


@dataclass
class FetchOutcome:
    """The result of fetching every curated board for one run."""

    fetched: list[FetchedJob] = field(default_factory=list)
    # (source value, token) pairs whose fetch succeeded — gates Silver deactivation.
    succeeded_boards: set[tuple[str, str]] = field(default_factory=set)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RunRecord:
    """Everything persisted to ``ingestion_runs`` for one pipeline run."""

    run_id: str
    trigger: str
    started_at: datetime
    finished_at: datetime
    status: str
    boards_attempted: int
    boards_succeeded: int
    raw_fetched: int
    jobs_upserted: int
    jobs_deactivated: int
    errors: list[str]


@dataclass(frozen=True)
class RunResult:
    """The summary returned to the caller (CLI / flow) after a run."""

    run_id: str
    status: str
    boards_attempted: int
    boards_succeeded: int
    raw_fetched: int
    jobs_upserted: int
    jobs_deactivated: int
    demand_rows: int
    errors: list[str]
