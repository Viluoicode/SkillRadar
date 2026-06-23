"""LLM learning-roadmap generator backed by the Anthropic Messages API.

This is the one place that talks to an LLM. It degrades gracefully: with no
``ANTHROPIC_API_KEY`` (or no ``anthropic`` package installed) ``generate()`` returns ``None``
and the dashboard still shows the data-driven gap. Results are cached on disk keyed by
(model, role, missing skills) so repeat requests don't re-bill.

Model is configurable via ``SKILLRADAR_LLM_MODEL`` (see :mod:`skillradar.infrastructure.config`)."""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Sequence
from pathlib import Path

from skillradar.domain.skillgap import GapSkill, Roadmap

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a pragmatic senior engineer mentoring a junior developer. Given a target role and "
    "the in-demand skills they are missing — each with the share of job postings that require it "
    "— produce a focused, ordered learning roadmap. Order by a sensible mix of demand and "
    "prerequisite flow (fundamentals before advanced specializations). Ground each step's "
    "rationale in the demand numbers provided. Be concrete and concise."
)


class AnthropicRoadmapGenerator:
    """Implements the ``LearningRoadmapGenerator`` port using Anthropic's SDK."""

    def __init__(
        self,
        model: str,
        cache_dir: Path,
        api_key: str | None = None,
        max_skills: int = 8,
    ) -> None:
        self._model = model
        self._cache_dir = Path(cache_dir)
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._max_skills = max_skills

    @property
    def available(self) -> bool:
        """True when an API key is configured (the UI uses this to show an enable hint)."""
        return bool(self._api_key)

    def generate(self, role: str, missing: Sequence[GapSkill]) -> Roadmap | None:
        if not self._api_key or not missing:
            return None

        top = list(missing)[: self._max_skills]
        cache_path = self._cache_path(role, top)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached

        try:
            import anthropic  # imported lazily so the package is only needed when generating
        except ImportError:
            logger.warning("anthropic package not installed; skipping roadmap generation")
            return None

        try:
            client = anthropic.Anthropic(api_key=self._api_key)
            response = client.messages.create(
                model=self._model,
                max_tokens=2000,
                system=_SYSTEM,
                messages=[{"role": "user", "content": self._build_prompt(role, top)}],
            )
            text = "".join(b.text for b in response.content if b.type == "text")
            roadmap = Roadmap.model_validate_json(_extract_json(text))
        except Exception as exc:  # any failure degrades to "no roadmap" rather than breaking the UI
            logger.warning("Roadmap generation failed: %s", exc)
            return None

        self._write_cache(cache_path, roadmap)
        return roadmap

    # ---- prompt ----------------------------------------------------------------
    @staticmethod
    def _build_prompt(role: str, missing: Sequence[GapSkill]) -> str:
        lines = [
            f"Target role: {role}",
            "",
            "Missing in-demand skills (skill — share of this role's postings that require it):",
        ]
        lines += [
            f"- {g.skill} — {g.share:.0%} of {role} postings ({g.job_count} jobs)" for g in missing
        ]
        lines += [
            "",
            "Return ONLY a JSON object (no prose, no markdown fence) of exactly this shape:",
            '{"role": str, "summary": str, '
            '"steps": [{"skill": str, "why": str, "resources": [str, ...]}]}',
            "One step per missing skill, ordered for learning. Each 'why' must cite the demand "
            "share. 'resources' = 1-3 concrete, well-known resources (free where possible).",
        ]
        return "\n".join(lines)

    # ---- cache -----------------------------------------------------------------
    def _cache_path(self, role: str, missing: Sequence[GapSkill]) -> Path:
        key = "|".join([self._model, role, *sorted(g.skill for g in missing)])
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return self._cache_dir / f"{digest}.json"

    def _read_cache(self, path: Path) -> Roadmap | None:
        if not path.exists():
            return None
        try:
            return Roadmap.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:  # a corrupt cache entry is non-fatal — regenerate
            return None

    def _write_cache(self, path: Path, roadmap: Roadmap) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(roadmap.model_dump_json(indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not write roadmap cache: %s", exc)


def _extract_json(text: str) -> str:
    """Best-effort: pull the outermost JSON object from the model's reply."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start : end + 1]
