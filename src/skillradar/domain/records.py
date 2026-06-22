"""Domain records that flow between the pipeline services and the persistence ports.

These are plain in-memory representations of the Silver/Gold rows — deliberately decoupled
from how (or whether) they are stored. Repositories translate between these records and the
DuckDB tables; the business rules in :mod:`skillradar.domain` and the application services
only ever touch these types.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

# Field order matches the ``jobs`` DDL so a repository can map a record to a row trivially.
JOB_FIELDS = (
    "job_id",
    "source",
    "source_job_id",
    "board_token",
    "company",
    "title",
    "location",
    "is_remote",
    "description",
    "apply_url",
    "posted_at",
    "dedup_hash",
    "first_seen_at",
    "last_seen_at",
    "is_active",
)


@dataclass
class JobRecord:
    """One row of the Silver ``jobs`` table. Mutable — the reconcile rules update lifecycle
    fields (``last_seen_at`` / ``is_active``) in place during a run."""

    job_id: str
    source: str
    source_job_id: str
    board_token: str
    company: str
    title: str
    location: str | None
    is_remote: bool
    description: str
    apply_url: str
    posted_at: datetime | None
    dedup_hash: str
    first_seen_at: datetime
    last_seen_at: datetime
    is_active: bool


@dataclass(frozen=True)
class JobText:
    """Just the text fields of a posting, used by skill extraction."""

    job_id: str
    title: str
    description: str


@dataclass(frozen=True)
class ActiveJob:
    """The slice of an active posting the Gold aggregation needs."""

    job_id: str
    title: str
    dedup_hash: str


@dataclass(frozen=True)
class SkillLink:
    """An extracted (job → skill) edge. ``category`` comes from the skill dictionary."""

    job_id: str
    skill: str
    category: str | None


@dataclass(frozen=True)
class DemandRow:
    """One aggregated demand cell: how many postings for ``role`` require ``skill``."""

    role: str
    skill: str
    category: str | None
    job_count: int
    snapshot_date: date
