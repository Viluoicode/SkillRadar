"""Greenhouse public job boards.

Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
Port of .NET ``GreenhouseJobSource``."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from ..common.dates import parse_iso
from ..common.models import FetchedJob, JobSource
from ..common.text import strip_html
from .json_helpers import get_child, get_id, get_str

BASE_URL = "https://boards-api.greenhouse.io/"


class GreenhouseConnector:
    source = JobSource.greenhouse

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def fetch(self, board_token: str) -> list[FetchedJob]:
        url = f"{BASE_URL}v1/boards/{quote(board_token, safe='')}/jobs?content=true"
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

            location = None
            loc = get_child(job, "location")
            if loc is not None:
                location = get_str(loc, "name")

            company = get_str(job, "company_name")
            results.append(
                FetchedJob(
                    source=self.source,
                    board_token=board_token,
                    source_job_id=job_id,
                    raw_json=_raw(job),
                    company=company if company and company.strip() else board_token,
                    title=get_str(job, "title") or "",
                    location=location,
                    remote=_looks_remote(location),
                    description=strip_html(get_str(job, "content")),
                    apply_url=get_str(job, "absolute_url") or "",
                    posted_at=parse_iso(
                        get_str(job, "updated_at") or get_str(job, "first_published")
                    ),
                )
            )
        return results


def _looks_remote(location: str | None) -> bool:
    return location is not None and "remote" in location.lower()


def _raw(job: object) -> str:
    import json

    return json.dumps(job, ensure_ascii=False)
