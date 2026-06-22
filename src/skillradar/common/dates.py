"""Lenient date parsing for ATS payloads."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp (with offset or trailing ``Z``) to an aware datetime,
    returning ``None`` on anything unparseable (mirrors .NET ``DateTimeOffset.TryParse``)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def from_epoch_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)
