"""Arbeitnow — a Tier-2 job aggregator (single global feed, no API key).

Endpoint: GET https://www.arbeitnow.com/api/job-board-api  (paginated via ``links.next``)

Unlike the ATS connectors, this is one global feed rather than a per-company board, so the
``board_token`` is ignored. Postings carry real company names (not the token), and overlap
with ATS postings is handled downstream by the cross-source dedup hash."""

from __future__ import annotations

import json

import httpx

from skillradar.domain.dates import from_epoch_ms
from skillradar.domain.models import FetchedJob, JobSource
from skillradar.domain.text import strip_html
from skillradar.infrastructure.sources.json_helpers import get_bool, get_id, get_str

BASE_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowConnector:
    source = JobSource.arbeitnow

    def __init__(self, client: httpx.Client, max_pages: int = 2) -> None:
        self._client = client
        self._max_pages = max(1, max_pages)

    def fetch(self, board_token: str) -> list[FetchedJob]:  # board_token ignored (global feed)
        results: list[FetchedJob] = []
        url: str | None = BASE_URL
        pages = 0

        while url and pages < self._max_pages:
            resp = self._client.get(url)
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, dict):
                break

            data = payload.get("data")
            if isinstance(data, list):
                results.extend(self._parse(job) for job in data if _has_id(job))

            links = payload.get("links")
            url = links.get("next") if isinstance(links, dict) else None
            pages += 1

        return results

    def _parse(self, job: dict) -> FetchedJob:
        company = get_str(job, "company_name")
        return FetchedJob(
            source=self.source,
            board_token="arbeitnow",
            source_job_id=get_id(job, "slug") or "",
            raw_json=json.dumps(job, ensure_ascii=False),
            company=company if company and company.strip() else "arbeitnow",
            title=get_str(job, "title") or "",
            location=get_str(job, "location"),
            remote=get_bool(job, "remote"),
            description=strip_html(get_str(job, "description")),
            apply_url=get_str(job, "url") or "",
            posted_at=_created_at(job),
        )


def _has_id(job: object) -> bool:
    return bool(get_id(job, "slug"))


def _created_at(job: dict) -> object | None:
    value = job.get("created_at")
    if isinstance(value, int) and not isinstance(value, bool):
        return from_epoch_ms(value * 1000)  # Arbeitnow timestamps are unix seconds
    return None
