"""Lever public postings.

Endpoint: GET https://api.lever.co/v0/postings/{token}?mode=json
Port of .NET ``LeverJobSource``."""

from __future__ import annotations

import json
from urllib.parse import quote

import httpx

from ..common.dates import from_epoch_ms
from ..common.models import FetchedJob, JobSource
from ..common.text import strip_html
from .json_helpers import get_child, get_id, get_str

BASE_URL = "https://api.lever.co/"


class LeverConnector:
    source = JobSource.lever

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def fetch(self, board_token: str) -> list[FetchedJob]:
        url = f"{BASE_URL}v0/postings/{quote(board_token, safe='')}?mode=json"
        resp = self._client.get(url)
        resp.raise_for_status()
        payload = resp.json()

        results: list[FetchedJob] = []
        if not isinstance(payload, list):
            return results

        for job in payload:
            job_id = get_id(job, "id")
            if not job_id:
                continue

            location = commitment = None
            cats = get_child(job, "categories")
            if cats is not None:
                location = get_str(cats, "location")
                commitment = get_str(cats, "commitment")

            # Prefer plain text; fall back to stripping the HTML description.
            description = get_str(job, "descriptionPlain")
            if not description or not description.strip():
                description = strip_html(get_str(job, "description"))

            workplace = get_str(job, "workplaceType")
            remote = (
                (workplace or "").lower() == "remote"
                or _looks_remote(location)
                or _looks_remote(commitment)
            )

            results.append(
                FetchedJob(
                    source=self.source,
                    board_token=board_token,
                    source_job_id=job_id,
                    raw_json=json.dumps(job, ensure_ascii=False),
                    company=board_token,
                    title=get_str(job, "text") or "",
                    location=location,
                    remote=remote,
                    description=description or "",
                    apply_url=get_str(job, "hostedUrl") or get_str(job, "applyUrl") or "",
                    posted_at=_parse_created_at(job),
                )
            )
        return results


def _looks_remote(value: str | None) -> bool:
    return value is not None and "remote" in value.lower()


def _parse_created_at(job: dict) -> object | None:
    value = job.get("createdAt")
    if isinstance(value, int) and not isinstance(value, bool):
        return from_epoch_ms(value)
    return None
