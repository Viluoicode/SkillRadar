# SkillRadar — Python (Data Engineering) edition

A read-only **job-market intelligence** pipeline. SkillRadar aggregates real tech job
postings from public ATS feeds (**Greenhouse, Lever, Ashby**), runs a **Medallion
(Bronze → Silver → Gold)** pipeline to ingest → normalize → dedupe, extracts required
skills with a rule-based dictionary, and serves a Streamlit dashboard of in-demand skills
per role plus a filterable job list. Every posting links to its original source.

This is the **Python rebuild** of the .NET SkillRadar (which lives in the parent folder).
Same product, modern DE stack — and it reuses the same `data/sources.json` board list and
`data/skills.seed.json` dictionary.

## Stack

| Concern | Tool |
| --- | --- |
| Ingestion / resilience | `httpx` + `tenacity` (retry/backoff, per-board isolation) |
| Validation | `pydantic` v2 |
| Transform + storage | `pandas` + **DuckDB** + Parquet (Medallion on local files) |
| Skill extraction | rule-based regex matcher + ambiguous-term guards (ported from .NET) |
| Orchestration | plain Python (`pipeline/run.py`) → **Prefect** (`pipeline/flow.py`) |
| Schedule / CI | GitHub Actions (cron + lint/test) |
| Dashboard | **Streamlit** + Altair |

## Architecture

```
Greenhouse · Lever · Ashby                (public ATS APIs)
        │  httpx + tenacity (retry, per-board isolation)
        ▼
BRONZE   data/bronze/run_*.parquet        raw payloads, exactly as fetched (replayable)
        │  pydantic + normalize + dedup + lifecycle
        ▼
SILVER   DuckDB: jobs, job_skills         typed, deduped (cross-source hash), first/last_seen + is_active
        │  regex skill matcher + guards, SQL aggregation
        ▼
GOLD     DuckDB: skill_demand,            in-demand skills per role per snapshot; accumulated trends
         skill_trends
        ▼
SERVING  Streamlit dashboard (reads Gold directly)
```

## Setup

```bash
cd python
uv venv && uv pip install -e ".[dev]"     # or: pip install -e ".[dev]"
```

## Run

```bash
# M0 spike — prove you can pull real data
uv run python m0_spike.py

# Full pipeline (Bronze → Silver → Gold) → writes data/skillradar.duckdb
uv run python -m skillradar.pipeline.run

# Inspect the result
duckdb data/skillradar.duckdb \
  "SELECT role, skill, job_count FROM skill_demand ORDER BY job_count DESC LIMIT 20"

# Dashboard
uv run streamlit run dashboard/app.py
```

### Orchestrated run (Prefect, optional)

```bash
uv pip install -e ".[orchestration]"
uv run python -m skillradar.pipeline.flow
```

## Tests & lint

```bash
uv run pytest
uv run ruff check .
```

The tests port the .NET suite for behavior parity: skill matcher + guards, the dedup hash,
the ATS connectors (mocked with `httpx.MockTransport`), and the Silver/Gold pipeline
(extraction, demand aggregation, cross-source dedup, job lifecycle).

## Configuration

Paths default to this folder's `data/`. Override with env vars when needed:

| Variable | Default |
| --- | --- |
| `SKILLRADAR_SOURCES` | `data/sources.json` |
| `SKILLRADAR_SKILLS` | `data/skills.seed.json` |
| `SKILLRADAR_DUCKDB` | `data/skillradar.duckdb` |
| `SKILLRADAR_BRONZE` | `data/bronze/` |
| `SKILLRADAR_DELAY_MS` | `500` (polite delay between board calls) |

Add or remove companies by editing `data/sources.json`; extend the dictionary via
`data/skills.seed.json`.

## Deployment (zero server cost)

- **GitHub Actions** (`.github/workflows/pipeline.yml`) runs the pipeline daily and commits
  the refreshed DuckDB + Parquet.
- **Streamlit Community Cloud** hosts `dashboard/app.py`, reading the committed data.

> The workflow files assume the `python/` folder is the repository root. If you keep this
> inside the larger repo, move `.github/workflows/*` to the repo root and add
> `working-directory: python` to each run step.

## Roadmap

Done: M0–M6 (ingestion → Bronze → Silver → Gold → dashboard → orchestration/CI) plus
`skill_trends` snapshots. Next: a trend chart and skill-gap input (your skills vs. demand)
in the dashboard; optional LLM enrichment for smarter skill/seniority extraction.
