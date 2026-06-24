"""\"Ask the market\" — a conversational agent answering job-market questions grounded in the
real DuckDB data via **structured tool-use** (no model-generated SQL).

Claude is given a fixed set of read-only tools that wrap :class:`DuckDbServingReadModel`; it
picks tools + args, we execute them, and it composes a grounded answer. Degrades gracefully:
with no ``ANTHROPIC_API_KEY`` (or no ``anthropic`` package) ``available`` is False and the
dashboard shows an enable hint instead of calling the agent.

Model is configurable via ``SKILLRADAR_LLM_MODEL`` (see :mod:`skillradar.infrastructure.config`)."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from skillradar.infrastructure.db.repositories import DuckDbServingReadModel, JobFilters

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are SkillRadar's market analyst. Answer questions about the tech job market using ONLY "
    "the provided tools, which query a database of real, current job postings aggregated from "
    "public ATS feeds (Greenhouse, Lever, Ashby).\n"
    "Rules:\n"
    "- Ground every answer in tool results. Cite concrete numbers, company names, and skills.\n"
    "- Resolve a loose skill term with resolve_skill before filtering by it; use exact role "
    "names from list_roles.\n"
    "- When listing jobs, give company + title; apply links come from apply_url.\n"
    "- If the tools can't answer (data unavailable, or the question is outside the job market), "
    "say so plainly — never guess or use outside knowledge.\n"
    "- Be concise: lead with the key numbers, keep prose short."
)

# Tool schemas exposed to Claude. Each maps to a read-only DuckDbServingReadModel call.
_TOOLS: list[dict[str, Any]] = [
    {
        "name": "market_overview",
        "description": "Dataset stats: number of active postings, distinct skills observed, and "
        "when data was last refreshed. Use for 'how many jobs / how fresh' questions.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_roles",
        "description": "The role families jobs are classified into (e.g. Data Engineer). Call "
        "this to get an exact role name before using top_skills_for_role.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "resolve_skill",
        "description": "Map a loose skill term to exact canonical skill names in the dataset "
        "(e.g. 'rust'->'Rust', 'ml'->'Machine Learning'). Resolve before filtering by skill.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "A skill term to look up."}},
            "required": ["query"],
        },
    },
    {
        "name": "top_skills_for_role",
        "description": "Most in-demand skills for a role family, with posting counts and the share "
        "(%) of that role's postings. Use exact role names from list_roles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "role": {"type": "string"},
                "limit": {"type": "integer", "description": "How many skills (default 15)."},
            },
            "required": ["role"],
        },
    },
    {
        "name": "find_jobs",
        "description": "Find active postings matching filters; returns the match count and a "
        "sample (company, title, location, remote, apply_url). Use exact skill names.",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "company": {"type": "string", "description": "Substring of company name."},
                "location": {"type": "string", "description": "Substring of location."},
                "remote": {"type": "string", "enum": ["any", "remote", "onsite"]},
                "title_contains": {"type": "string"},
                "limit": {"type": "integer", "description": "Max jobs to return (default 10)."},
            },
        },
    },
    {
        "name": "companies_hiring",
        "description": "Top companies by number of active postings, optionally restricted to jobs "
        "requiring a given skill. Use exact skill names from resolve_skill.",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill": {"type": "string"},
                "limit": {"type": "integer", "description": "How many companies (default 10)."},
            },
        },
    },
]

_REMOTE_MAP = {"remote": "Remote only", "onsite": "On-site only", "any": "Any"}


@dataclass(frozen=True)
class ChatResult:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    available: bool = True


class MarketChatAgent:
    """Grounded Q&A over the warehouse via Claude tool-use. Lightweight: holds a reference to
    the read model (no own connection), so construct it per request rather than caching."""

    def __init__(
        self,
        read_model: DuckDbServingReadModel,
        model: str,
        api_key: str | None = None,
        skill_resolver: Callable[[str], list[str]] | None = None,
        max_iterations: int = 5,
        max_tokens: int = 1500,
    ) -> None:
        self._rm = read_model
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        # Alias-aware resolver (the skill matcher); falls back to substring over canonical names.
        self._resolver = skill_resolver
        self._max_iterations = max_iterations
        self._max_tokens = max_tokens

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    def answer(self, question: str) -> ChatResult:
        if not self._api_key:
            return ChatResult(text="", available=False)

        try:
            import anthropic  # lazy — only needed when actually answering
        except ImportError:
            logger.warning("anthropic package not installed; market chat disabled")
            return ChatResult(text="", available=False)

        client = anthropic.Anthropic(api_key=self._api_key)
        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
        tool_calls: list[dict[str, Any]] = []

        try:
            for _ in range(self._max_iterations):
                resp = client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=_SYSTEM,
                    tools=_TOOLS,
                    messages=messages,
                )
                if resp.stop_reason != "tool_use":
                    text = "".join(b.text for b in resp.content if b.type == "text")
                    return ChatResult(text=text, tool_calls=tool_calls)

                messages.append({"role": "assistant", "content": resp.content})
                results = []
                for block in resp.content:
                    if block.type != "tool_use":
                        continue
                    out = self._dispatch(block.name, dict(block.input or {}))
                    tool_calls.append({"name": block.name, "input": dict(block.input or {})})
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(out, default=str),
                        }
                    )
                messages.append({"role": "user", "content": results})
        except Exception as exc:  # network/API failure → friendly message, never crash the app
            logger.warning("Market chat failed: %s", exc)
            return ChatResult(text=f"Sorry, the query failed: {exc}", tool_calls=tool_calls)

        return ChatResult(
            text="I needed too many steps to answer that — try a more specific question.",
            tool_calls=tool_calls,
        )

    # ---- pure dispatcher (unit-tested without a network call) ------------------
    def _dispatch(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        rm = self._rm
        try:
            if name == "market_overview":
                s = rm.stats()
                row = s.to_dict("records")[0] if not s.empty else {}
                last = row.get("last_run")
                return {
                    "active_jobs": int(row.get("active_jobs") or 0),
                    "skills_observed": int(row.get("skills_seen") or 0),
                    "last_refresh": None if last is None else str(last)[:16],
                }
            if name == "list_roles":
                return {"roles": rm.roles_latest()["role"].tolist()}
            if name == "resolve_skill":
                q = str(args.get("query", ""))
                if self._resolver is not None:
                    return {"matches": list(self._resolver(q))[:15]}
                ql = q.lower()
                return {"matches": [s for s in rm.distinct_skills() if ql in s.lower()][:15]}
            if name == "top_skills_for_role":
                role = str(args["role"])
                limit = int(args.get("limit", 15))
                total = rm.role_total(role)
                rows = rm.demand(role, limit).to_dict("records")
                skills = [
                    {
                        "skill": r["skill"],
                        "category": r["category"],
                        "job_count": int(r["job_count"]),
                        "share_pct": round(100 * r["job_count"] / total, 1) if total else 0.0,
                    }
                    for r in rows
                ]
                return {"role": role, "role_postings": total, "skills": skills}
            if name == "find_jobs":
                f = JobFilters(
                    skill=args.get("skill"),
                    company=args.get("company"),
                    location=args.get("location"),
                    remote=_REMOTE_MAP.get(str(args.get("remote", "any")).lower(), "Any"),
                    search=args.get("title_contains"),
                )
                total = rm.job_count(f)
                limit = max(1, min(int(args.get("limit", 10)), 25))
                jobs = [
                    {
                        "company": r["company"],
                        "title": r["title"],
                        "location": r["location"],
                        "remote": bool(r["is_remote"]),
                        "apply_url": r["apply_url"],
                    }
                    for r in rm.jobs_page(f, limit, 0).to_dict("records")
                ]
                return {"total_matches": total, "jobs": jobs}
            if name == "companies_hiring":
                rows = rm.companies_hiring(
                    skill=args.get("skill"), limit=int(args.get("limit", 10))
                ).to_dict("records")
                return {
                    "companies": [
                        {"company": r["company"], "job_count": int(r["job_count"])} for r in rows
                    ]
                }
            return {"error": f"unknown tool: {name}"}
        except Exception as exc:  # a bad arg shouldn't abort the loop — report it to the model
            return {"error": f"{name} failed: {exc}"}
