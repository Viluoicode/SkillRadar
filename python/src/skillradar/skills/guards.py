"""Precision guards for ambiguous skill terms.

Port of the .NET ``SkillGuard``. After a short, word-like term ("C", "R", "Go") matches,
the occurrence is rejected when the immediately surrounding text matches a "this isn't the
skill" pattern ("C-level", "R&D", "Go-to-Market"), while real language-list mentions are
kept. The skill is still recorded if any *other* occurrence in the text passes."""

from __future__ import annotations

import re

_OPTS = re.IGNORECASE


class SkillGuard:
    def __init__(
        self, term: str, reject_before: str | None = None, reject_after: str | None = None
    ):
        self.term = term
        # ``reject_before`` is anchored with ``$`` (tested against text ending at the match
        # start); ``reject_after`` with ``^`` (tested against text starting at the match end).
        self._reject_before = re.compile(reject_before, _OPTS) if reject_before else None
        self._reject_after = re.compile(reject_after, _OPTS) if reject_after else None

    def rejects(self, text: str, start: int, length: int) -> bool:
        if self._reject_after is not None and self._reject_after.search(text[start + length :]):
            return True
        if self._reject_before is not None:
            tail = min(16, start)  # a short tail is enough context and keeps the scan bounded
            if self._reject_before.search(text[start - tail : start]):
                return True
        return False


# Built-in guards for the ambiguous single/short terms in the seeded dictionary,
# calibrated against real ATS descriptions (identical to the .NET defaults).
DEFAULT_GUARDS: list[SkillGuard] = [
    SkillGuard(
        "C",
        reject_before=r"([A-Za-z]\.|\bseries )$",
        reject_after=r"^([\s‑-]?(?:level|suite)\b|['’])",
    ),
    SkillGuard("R", reject_after=r"^[&$]"),
    SkillGuard("Go", reject_before=r"\byou $", reject_after=r"^-(?:to-market|live)"),
]
