"""Ashby public job boards.

Endpoint: GET https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true
Port of .NET ``AshbyJobSource``."""

from __future__ import annotations

import json
from urllib.parse import quote

import httpx

from skillradar.domain.dates import parse_iso
from skillradar.domain.models import FetchedJob, JobSource
from skillradar.domain.text import strip_html
from skillradar.infrastructure.sources.json_helpers import get_bool, get_id, get_str

BASE_URL = "https://api.ashbyhq.com/"


class AshbyConnector:
    source = JobSource.ashby

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def fetch(self, board_token: str) -> list[FetchedJob]:
        url = (
            f"{BASE_URL}posting-api/job-board/{quote(board_token, safe='')}"
            "?includeCompensation=true"
        )
        resp = self._client.get(url)
        resp.raise_for_status()
        payload = resp.json()

        results: list[FetchedJob] = []
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            return results

        for job in jobs:
            job_id = get_id(job, "id")
            if not job_id:
                continue

            description = get_str(job, "descriptionPlain")
            if not description or not description.strip():
                description = strip_html(get_str(job, "descriptionHtml"))

            results.append(
                FetchedJob(
                    source=self.source,
                    board_token=board_token,
                    source_job_id=job_id,
                    raw_json=json.dumps(job, ensure_ascii=False),
                    company=board_token,
                    title=get_str(job, "title") or "",
                    location=get_str(job, "location"),
                    remote=get_bool(job, "isRemote"),
                    description=description or "",
                    apply_url=get_str(job, "jobUrl") or get_str(job, "applyUrl") or "",
                    posted_at=parse_iso(get_str(job, "publishedAt")),
                )
            )
        return results
