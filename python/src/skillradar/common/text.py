"""Text helpers for cleaning ATS payloads and building dedup keys.

Port of the .NET ``TextNormalizer`` (SkillRadar.Core/Text/TextNormalizer.cs)."""

from __future__ import annotations

import html
import re

_HTML_TAG = re.compile(r"<[^>]+>", re.S)
_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]")


def strip_html(value: str | None) -> str:
    """Convert ATS HTML (which may be entity-encoded) to plain text: decode entities
    first so encoded tags become real tags, then strip tags and collapse whitespace."""
    if not value or not value.strip():
        return ""
    decoded = html.unescape(value)
    without_tags = _HTML_TAG.sub(" ", decoded)
    return _WHITESPACE.sub(" ", without_tags).strip()


def normalize_for_key(value: str | None) -> str:
    """Stable comparison key: lower-cased, punctuation removed, whitespace collapsed.
    Used to build the cross-source dedup hash from (company + title + location)."""
    if not value or not value.strip():
        return ""
    lowered = value.strip().lower()
    cleaned = _NON_ALNUM.sub(" ", lowered)
    return _WHITESPACE.sub(" ", cleaned).strip()
