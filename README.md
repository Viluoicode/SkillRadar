# SkillRadar — Python (Data Engineering) edition

A read-only **job-market intelligence** pipeline. SkillRadar aggregates real tech job
postings from public ATS feeds (**Greenhouse, Lever, Ashby**), runs a **Medallion
(Bronze → Silver → Gold)** pipeline to ingest → normalize → dedupe, extracts required
skills with a rule-based dictionary, and serves a Streamlit dashboard of in-demand skills
per role plus a filterable job list. Every posting links to its original source.

This is the **active product**. The original ASP.NET Core implementation is archived for
reference at [`reference/dotnet-original/`](reference/dotnet-original/) (the Python parity
tests were ported from it); it is not built or tested in CI.

## Stack

| Concern | Tool |
| --- | --- |
| Ingestion / resilience | `httpx` + `tenacity` (retry/backoff, per-board isolation) |
| Validation | `pydantic` v2 |
| Transform + storage | `pandas` + **DuckDB** + Parquet (Medallion on local files) |
| Skill extraction | rule-based regex matcher + ambiguous-term guards (ported from .NET) |
| Orchestration | plain Python (`interface/cli.py`) → **Prefect** (`interface/prefect_flow.py`) |
| Schedule / CI | GitHub Actions (cron + lint/test) |
| Dashboard | **Streamlit** + Altair |

## Architecture

Two views of the same system — the Medallion **data flow**, and the Clean-Architecture
**code layers** it runs on.

```
Greenhouse · Lever · Ashby                (public ATS APIs)
        │  httpx + tenacity (retry, per-board isolation)
        ▼
BRONZE   data/bronze/run_*.parquet        raw payloads, exactly as fetched (replayable)
        │  pydantic + normalize + dedup + lifecycle
        ▼
SILVER   DuckDB: jobs, job_skills         typed, deduped (cross-source hash), first/last_seen + is_active
        │  regex skill matcher + guards, role aggregation
        ▼
GOLD     DuckDB: skill_demand,            in-demand skills per role per snapshot; accumulated trends
         skill_trends
        ▼
SERVING  Streamlit dashboard (reads Gold through a read-model repository)
```

The code is organized into four layers with a strict **inward** dependency rule
(`interface → infrastructure → application → domain`):

```
src/skillradar/
├── domain/          pure rules & types — models, records, dedup/text/dates, roles, skills
│                    matcher/guards, and the reconciliation/extraction/demand algorithms.
│                    Imports only the stdlib + pydantic. No duckdb/httpx/pandas, ever.
├── application/     use-cases + ports — repository/connector Protocols (ports.py), DTOs,
│                    errors, the silver/skills/gold services, and the pipeline orchestrator.
│                    Depends only on domain.
├── infrastructure/  the only layer that touches I/O — DuckDb* repositories (all SQL lives
│                    here), warehouse schema, http client, Parquet bronze store, ATS
│                    connectors + board fetcher, JSON catalogs, config, logging.
└── interface/       composition roots — CLI (cli.py) and Prefect flow wire concrete
                     adapters into the pipeline. The Streamlit dashboard (dashboard/app.py)
                     renders through a read-model repository.
```

Why it matters: business rules never depend on DuckDB, so the whole Silver→Gold flow runs
against in-memory fakes in tests (`tests/test_services_with_fakes.py`), and the storage or
HTTP stack can change without touching `domain`/`application`. The dependency rule is
enforced by `tests/test_architecture.py`.

## Setup

```bash
# from the repository root
uv venv && uv pip install -e ".[dev]"     # or: pip install -e ".[dev]"
```

Python **3.12+** required.

## Run

```bash
# M0 spike — prove you can pull real data
python m0_spike.py

# Full pipeline (Bronze → Silver → Gold) → writes data/skillradar.duckdb
python -m skillradar.interface.cli            # or just: skillradar

# Inspect the result
duckdb data/skillradar.duckdb \
  "SELECT role, skill, job_count FROM skill_demand \
   WHERE snapshot_date = (SELECT max(snapshot_date) FROM skill_demand) \
   ORDER BY job_count DESC LIMIT 20"

# Dashboard
streamlit run dashboard/app.py
```

### Orchestrated run (Prefect, optional)

```bash
uv pip install -e ".[orchestration]"
python -m skillradar.interface.prefect_flow
```

## Tests & lint

```bash
pytest
ruff check .
```

The tests port the .NET suite for behavior parity (skill matcher + guards, the dedup hash,
the ATS connectors mocked with `httpx.MockTransport`, and the Silver/Gold pipeline) and add
two architecture-focused tests: the services running against in-memory fake repositories,
and a scan that enforces the layer dependency rule.

## Configuration

Paths default to the repo's `data/`. Override with env vars when needed:

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

## Roadmap

Done: M0–M6 (ingestion → Bronze → Silver → Gold → dashboard → orchestration/CI) plus
`skill_trends` snapshots, then a full Clean-Architecture restructure. Next: a trend chart
and skill-gap input (your skills vs. demand) in the dashboard; optional LLM enrichment for
smarter skill/seniority extraction.
