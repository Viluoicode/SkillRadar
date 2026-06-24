# SkillRadar — Python (Data Engineering) edition

A read-only **job-market intelligence** pipeline. SkillRadar aggregates real tech job
postings from public ATS feeds (**Greenhouse, Lever, Ashby**) plus the **Arbeitnow**
aggregator, runs a **Medallion (Bronze → Silver → Gold)** pipeline to ingest → normalize →
dedupe, extracts required skills with a rule-based dictionary, and serves a Streamlit
dashboard of in-demand skills per role plus a filterable job list. Every posting links to
its original source. The curated `data/sources.json` ships 35 ATS company boards + 1
aggregator (~6.7k live postings, 130+ companies).

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

**One command — start the dashboard; refresh from the UI:**

```bash
streamlit run dashboard/app.py
```

The first time (no data yet) the dashboard prompts you to click **🔄 Refresh data** in the
sidebar — that runs the full Bronze → Silver → Gold pipeline in-process (~1–2 min) and reloads
with fresh jobs. Click it any time to pull the latest postings. No separate pipeline command
needed.

For headless / scheduled use (the daily CI cron uses this), run the pipeline directly:

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
| `SKILLRADAR_LLM_MODEL` | `claude-haiku-4-5` (AI roadmap + Ask tab) |
| `SKILLRADAR_ROADMAP_CACHE` | `data/roadmap_cache/` |
| `SKILLRADAR_SERVE_ONLY` | unset; set to `1` on hosted deploys to hide the Refresh button |
| `ANTHROPIC_API_KEY` | unset; enables AI features (or paste a key in the sidebar) |

Add or remove companies by editing `data/sources.json`; extend the dictionary via
`data/skills.seed.json`.

## Deployment (zero server cost)

The app runs on **Streamlit Community Cloud** reading a small committed snapshot — no server, no
database to host. Two pieces:

- **Data**: GitHub Actions (`.github/workflows/pipeline.yml`) runs the pipeline daily and commits
  a slim **`data/serving.duckdb`** — a compact, description-free copy (a few MB, vs. the bloated
  full warehouse) produced by `skillradar --export-serving`. That committed file is what the hosted
  app serves. The full working warehouse and Bronze Parquet stay untracked.
- **App**: Streamlit Community Cloud hosts `dashboard/app.py`, reading `serving.duckdb` from the
  repo (it falls back to the full local DB when present, so dev is unaffected).

### Deploy steps

1. Push the source manifests to GitHub (`requirements.txt`, `.python-version`,
   `.streamlit/config.toml`). The serving DB itself is a generated artifact (gitignored) — the
   daily Action commits it; trigger it once now via the **Actions → Pipeline → Run workflow**
   button so the first snapshot lands. (Locally you can preview it with
   `python -m skillradar.interface.cli --export-serving`.)
2. On [share.streamlit.io](https://share.streamlit.io) create an app → point it at
   `dashboard/app.py` on the `main` branch.
3. In the app's **Settings → Secrets**, add `SKILLRADAR_SERVE_ONLY = "1"`. This hides the in-app
   Refresh button (the hosted filesystem is ephemeral) — refreshes come from the daily cron.

### AI features on the public URL (bring-your-own-key)

The **Ask** tab and the AI roadmap need an Anthropic key. To keep the public deployment free for
the owner, the app uses **bring-your-own-key**: each visitor pastes *their own* key into the
sidebar (kept in their browser session only, never stored). Without a key, Explore and Skill-gap
work fully. Locally you can instead set `ANTHROPIC_API_KEY` in the environment.

## Roadmap

Done: M0–M6 (ingestion → Bronze → Silver → Gold → dashboard → orchestration/CI), a full
Clean-Architecture restructure, the Definition-of-Done source coverage (35 ATS boards + the
Arbeitnow aggregator), **M7** (demand-trend chart over daily `skill_trends` snapshots),
**M8** (skill-gap input + optional AI learning roadmap), **M9** (the *Ask the market* chat —
grounded Q&A via structured tool-use over the corpus), and the **Streamlit Community Cloud
deployment** (slim committed serving DB + bring-your-own-key AI).
Next: optional LLM enrichment for smarter skill/seniority extraction; semantic résumé→jobs
matching; a weekly AI market brief.

### Adding a new source

The Clean-Architecture split makes this a small, contained change: add a value to
`JobSource` (`domain/models.py`), write a connector implementing the `JobSourceConnector`
port under `infrastructure/sources/`, register it in `build_registry` (`sources/registry.py`),
and add board entries to `data/sources.json`. The `Arbeitnow` aggregator connector is a
worked example (a single global feed rather than a per-company board).
