"""Cross-source content hash used as the dedup fallback.

Port of the .NET ``DedupHasher`` (SkillRadar.Core/Text/DedupHasher.cs). Two postings of
the same role (same company, title, location) produce the same hash even across sources."""

from __future__ import annotations

import hashlib

from skillradar.domain.text import normalize_for_key


def compute_dedup_hash(company: str, title: str, location: str | None) -> str:
    key = "|".join(
        (
            normalize_for_key(company),
            normalize_for_key(title),
            normalize_for_key(location),
        )
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest().upper()


def make_job_id(source: str, source_job_id: str) -> str:
    """Stable surrogate key for a posting: hash of (source, source_job_id)."""
    return hashlib.sha256(f"{source}|{source_job_id}".encode()).hexdigest()
