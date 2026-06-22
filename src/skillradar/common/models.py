"""Canonical data shapes shared across the pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class JobSource(StrEnum):
    """The ATS platform a posting was ingested from."""

    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"


class FetchedJob(BaseModel):
    """A single posting from a connector: the verbatim raw payload (Bronze) plus the
    fields parsed into a canonical shape (Silver). Mirrors .NET ``FetchedJob``."""

    source: JobSource
    board_token: str
    source_job_id: str
    raw_json: str
    company: str
    title: str
    location: str | None = None
    remote: bool = False
    description: str = ""
    apply_url: str = ""
    posted_at: datetime | None = None
