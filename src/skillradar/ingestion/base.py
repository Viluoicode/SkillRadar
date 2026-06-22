"""Connector contract + curated-board config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..common.models import FetchedJob, JobSource


class JobSourceConnector(Protocol):
    """A connector to one ATS platform. ``fetch`` returns all live postings for a single
    board token in the canonical :class:`FetchedJob` shape, and must surface transport
    failures as exceptions so the pipeline can isolate a failing board."""

    source: JobSource

    def fetch(self, board_token: str) -> list[FetchedJob]: ...


@dataclass(frozen=True)
class BoardConfig:
    """One curated company board to ingest (from data/sources.json)."""

    source: JobSource
    token: str
    company: str | None = None
