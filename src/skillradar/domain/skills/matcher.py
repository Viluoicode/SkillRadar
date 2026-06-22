"""Rule-based, dictionary-driven skill extractor.

Port of the .NET ``SkillMatcher``. Compiles all skill terms into a single case-insensitive
regex with token boundaries that respect characters common in tech terms — so "C#", ".NET",
"C++", "Node.js" match, while "Go" does not match inside "Google" and "JS" not inside "JSON".
A literal "." is **not** a boundary char, so a term still matches when followed by a
sentence-ending period ("…we use Python.")."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from skillradar.domain.skills.guards import SkillGuard

# A term only matches when not flanked by one of these (word-style boundaries that still
# treat #, + as part of a token).
_TOKEN_CHAR = "A-Za-z0-9+#"


@dataclass(frozen=True)
class SkillTerms:
    """A canonical skill plus every surface form (name + aliases) that should match it."""

    skill_id: int
    canonical_name: str
    terms: tuple[str, ...]


class SkillMatcher:
    def __init__(
        self,
        skills: Iterable[SkillTerms],
        guards: Iterable[SkillGuard] | None = None,
    ) -> None:
        # Keys are lower-cased surface terms (case-insensitive matching).
        self._term_to_skill: dict[str, int] = {}
        self._guards: dict[str, SkillGuard] = {}
        for guard in guards or ():
            self._guards.setdefault(guard.term.lower(), guard)

        for skill in skills:
            for term in skill.terms:
                trimmed = term.strip()
                if not trimmed:
                    continue
                # First definition of a term wins; ignore duplicate alias collisions.
                self._term_to_skill.setdefault(trimmed.lower(), skill.skill_id)

        if not self._term_to_skill:
            self._regex = re.compile(r"(?!)")  # never matches
            return

        # Longer terms first so "Node.js" wins over "Node" at the same position.
        alternation = "|".join(
            re.escape(term)
            for term in sorted(self._term_to_skill, key=len, reverse=True)
        )
        pattern = rf"(?<![{_TOKEN_CHAR}])(?:{alternation})(?![{_TOKEN_CHAR}])"
        self._regex = re.compile(pattern, re.IGNORECASE)

    def match(self, text: str | None) -> set[int]:
        """Return the distinct skill ids mentioned anywhere in ``text``."""
        found: set[int] = set()
        if not text or not text.strip():
            return found

        for m in self._regex.finditer(text):
            value = m.group()
            skill_id = self._term_to_skill.get(value.lower())
            if skill_id is None:
                continue
            # An ambiguous term only counts when its context isn't a known false positive.
            guard = self._guards.get(value.lower())
            if guard is not None and guard.rejects(text, m.start(), len(value)):
                continue
            found.add(skill_id)

        return found
