"""Port of the .NET ConnectorTests using httpx MockTransport."""

from datetime import UTC, datetime

import httpx
import pytest

from skillradar.common.models import JobSource
from skillradar.ingestion.ashby import AshbyConnector
from skillradar.ingestion.greenhouse import GreenhouseConnector
from skillradar.ingestion.lever import LeverConnector


def client_returning(body: str, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_greenhouse_parses_postings():
    body = """
    {
      "jobs": [
        {
          "id": 12345,
          "title": "Senior Backend Engineer",
          "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
          "updated_at": "2026-05-01T10:00:00-04:00",
          "location": { "name": "Remote - US" },
          "company_name": "Acme",
          "content": "&lt;p&gt;We use &lt;b&gt;Go&lt;/b&gt; and Kubernetes.&lt;/p&gt;"
        }
      ]
    }
    """
    jobs = GreenhouseConnector(client_returning(body)).fetch("acme")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == JobSource.greenhouse
    assert job.source_job_id == "12345"
    assert job.title == "Senior Backend Engineer"
    assert job.company == "Acme"
    assert job.location == "Remote - US"
    assert job.remote is True
    assert job.apply_url == "https://boards.greenhouse.io/acme/jobs/12345"
    assert "Go" in job.description and "Kubernetes" in job.description
    assert "<p>" not in job.description  # HTML stripped
    assert job.posted_at is not None


def test_lever_parses_postings():
    body = """
    [
      {
        "id": "abc-123",
        "text": "Data Engineer",
        "hostedUrl": "https://jobs.lever.co/acme/abc-123",
        "categories": { "location": "New York", "commitment": "Full-time" },
        "descriptionPlain": "Build pipelines with Python and Spark.",
        "workplaceType": "onsite",
        "createdAt": 1714564800000
      }
    ]
    """
    jobs = LeverConnector(client_returning(body)).fetch("acme")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == JobSource.lever
    assert job.source_job_id == "abc-123"
    assert job.title == "Data Engineer"
    assert job.location == "New York"
    assert job.remote is False
    assert "Python" in job.description
    assert job.posted_at == datetime.fromtimestamp(1714564800, tz=UTC)


def test_ashby_parses_postings():
    body = """
    {
      "jobs": [
        {
          "id": "f1e2",
          "title": "ML Engineer",
          "location": "San Francisco",
          "isRemote": true,
          "descriptionPlain": "Work with PyTorch and TensorFlow.",
          "jobUrl": "https://jobs.ashbyhq.com/acme/f1e2",
          "publishedAt": "2026-04-15T00:00:00Z"
        }
      ]
    }
    """
    jobs = AshbyConnector(client_returning(body)).fetch("acme")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.source == JobSource.ashby
    assert job.source_job_id == "f1e2"
    assert job.title == "ML Engineer"
    assert job.remote is True
    assert "PyTorch" in job.description
    assert job.apply_url == "https://jobs.ashbyhq.com/acme/f1e2"


def test_connector_throws_on_http_error():
    source = GreenhouseConnector(client_returning("nope", status=500))
    with pytest.raises(httpx.HTTPStatusError):
        source.fetch("acme")
