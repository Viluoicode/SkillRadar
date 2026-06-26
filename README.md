# SkillRadar — Python (Data Engineering) edition

A read-only **job-market intelligence** pipeline. SkillRadar aggregates real tech job
postings from public ATS feeds (**Greenhouse, Lever, Ashby**) plus the **Arbeitnow**
aggregator, runs a **Medallion (Bronze → Silver → Gold)** pipeline to ingest → normalize →
dedupe, extracts required skills with a rule-based dictionary, and serves a Streamlit
dashboard of in-demand skills per role plus a filterable job list. Every posting links to
its original source. The curated `data/sources.json` ships 35 ATS company boards + 1
aggregator (~6.7k live postings, 130+ companies).

This is the **active product**. The original ASP.NET Core implementation (the Python parity tests
were ported from it) was **removed from `main`** and preserved at the git tag **`dotnet-archive`**
— see [`reference/README.md`](reference/README.md) to recover it. It is not built or tested in CI.

The **Silver → Gold** transform is built with **dbt** (a conformed star schema + the Gold marts);
see [Analytics engineering](#analytics-engineering-dbt) below and [`transform/`](transform/).

## Stack

| Concern | Tool |
| --- | --- |
| Ingestion / resilience | `httpx` + `tenacity` (retry/backoff, per-board isolation) |
| Validation | `pydantic` v2 |
| Load + storage | `pandas` + **DuckDB** / **MotherDuck** + Parquet (Bronze on local files) |
| Analytics engineering | **dbt** (`dbt-duckdb`) — Silver→Gold star schema, marts, tests, docs |
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
        │  regex skill matcher (Python)  →  dbt builds Silver → Gold
        ▼
GOLD     dbt star schema + marts          dims: company / skill / role / date · facts: job_posting, job_skill
         (skill_demand, skill_trends)     marts: demand leaderboard per role + accumulated trends
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
├── infrastructure/  the only layer that touches I/O — DuckDb* repositories (all *serving* SQL
│                    lives here), warehouse schema, http client, Parquet bronze store, ATS
│                    connectors + board fetcher, the dbt runner, JSON catalogs, config, logging.
└── interface/       composition roots — CLI (cli.py) and Prefect flow wire concrete
                     adapters into the pipeline. The Streamlit dashboard (dashboard/app.py)
                     renders through a read-model repository.
```

The offline **Silver→Gold transform lives in [`transform/`](transform/)** (dbt), outside the
Python layers — the pipeline shells out to it via the dbt runner
([`infrastructure/dbt/runner.py`](src/skillradar/infrastructure/dbt/runner.py)).

Why it matters: business rules never depend on DuckDB, so the whole Silver→Gold flow runs
against in-memory fakes in tests (`tests/test_services_with_fakes.py`), and the storage or
HTTP stack can change without touching `domain`/`application`. The dependency rule is
enforced by `tests/test_architecture.py`.

## Analytics engineering (dbt)

The warehouse **Silver → Gold** transform is a **dbt** project in [`transform/`](transform/). The
split is the modern data stack's: **Python does EL** (Bronze → Silver: fetch, validate, dedup,
lifecycle, regex skill extraction → writes `jobs` / `job_skills`), and **dbt does T** — a conformed
**star schema** and the Gold marts, with declarative tests and lineage docs.

```
staging            marts/core  (STAR SCHEMA)                  marts/analytics (Gold)
stg_jobs ───────┬─ dim_company  dim_skill  dim_role  dim_date   skill_demand   (leaderboard)
stg_job_skills ─┤  fact_job_posting ─► fact_job_skill           skill_trends
seed_roles ─────┴────────────── int_posting_roles ────────────► (serve the dashboard directly)
```

- **`fact_job_posting`** — one active, hash-deduped posting; FKs to `dim_company` / `dim_date`.
- **`fact_job_skill`** — bridge (posting × skill); FKs to `dim_skill` / `fact_job_posting`.
- **`skill_demand` / `skill_trends`** — Gold marts, aliased to the table names the dashboard
  already reads (the serving layer is unchanged). They reproduce the Python aggregation **exactly**
  — guaranteed by `tests/test_dbt_parity.py` (a real `dbt build` compared row-for-row).
- **Data quality** — `dbt build` runs `not_null` / `unique` on dim keys, `relationships` fact→dim,
  and `accepted_values` on `source` / `role` / skill `category`; `jobs` has source **freshness**.

```bash
pip install "dbt-duckdb>=1.9"                                   # dbt lives in its own env (3.12)
dbt build --project-dir transform --profiles-dir transform     # build + test the warehouse
dbt docs generate --project-dir transform --profiles-dir transform   # then `dbt docs serve` → DAG
```

In normal use the pipeline drives dbt for you: `skillradar --gold dbt` runs Bronze→Silver in
Python, then `dbt build` for Gold (falling back to the Python aggregation where dbt isn't
installed). Details: [`.claude/docs/dbt_transform.md`](.claude/docs/dbt_transform.md) ·
[`transform/README.md`](transform/README.md).

> 📸 *Run `dbt docs serve` and drop the lineage-graph screenshot here.*

## Setup

```bash
# from the repository root
uv venv && uv pip install -e ".[dev]"     # or: pip install -e ".[dev]"
```

Python **3.12+** required. For the dbt layer, also `pip install -e ".[dbt]"` (or keep it in a
separate env — dbt-core has no Python 3.14 wheels yet).

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
#   Gold engine: --gold auto (default; dbt when installed, else Python) | --gold dbt | --gold python

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
| `SKILLRADAR_DUCKDB` | `data/skillradar.duckdb` (local dev; ignored when MotherDuck is set) |
| `MOTHERDUCK_TOKEN` | unset; when set, the warehouse is MotherDuck (`md:<db>`) instead of a file |
| `SKILLRADAR_MOTHERDUCK_DB` | `skillradar` (MotherDuck database name) |
| `SKILLRADAR_BRONZE` | `data/bronze/` |
| `SKILLRADAR_DELAY_MS` | `500` (polite delay between board calls) |
| `SKILLRADAR_LLM_MODEL` | `claude-haiku-4-5` (AI roadmap + Ask tab) |
| `SKILLRADAR_ROADMAP_CACHE` | `data/roadmap_cache/` |
| `SKILLRADAR_SERVE_ONLY` | unset; set to `1` on hosted deploys to hide the Refresh button |
| `ANTHROPIC_API_KEY` | unset; enables AI features (or paste a key in the sidebar) |

Add or remove companies by editing `data/sources.json`; extend the dictionary via
`data/skills.seed.json`.

## Deployment

The production data layer is **MotherDuck** (DuckDB-in-the-cloud) — the same SQL runs unchanged,
and **no data is committed to git**. The pipeline writes to MotherDuck; the dashboard reads from
it. Locally (no token) everything falls back to a DuckDB file, so dev is unchanged.

- **Data**: GitHub Actions (`.github/workflows/pipeline.yml`) runs the pipeline daily (Silver in
  Python, **Gold via `dbt build` + dbt tests**) and writes straight to MotherDuck
  (`MOTHERDUCK_TOKEN` secret). On failure it pings an optional alert webhook.
- **App**: Streamlit Community Cloud hosts `dashboard/app.py`, reading the same MotherDuck database.
- **Switch**: `data_target()` ([config.py](src/skillradar/infrastructure/config.py)) returns
  `md:<db>` when `MOTHERDUCK_TOKEN` is set, else the local file path. One choke point, no SQL
  changes (all queries flow through `connect()` in
  [warehouse.py](src/skillradar/infrastructure/db/warehouse.py)).

### Deploy steps

1. Create a MotherDuck account (free tier), a database, and an access token.
2. **GitHub** → repo Secrets: add `MOTHERDUCK_TOKEN` (and optionally `ALERT_WEBHOOK` for failure
   pings). Run the **Actions → Pipeline → Run workflow** once to populate MotherDuck.
3. **Streamlit Cloud** ([share.streamlit.io](https://share.streamlit.io)) → new app on
   `dashboard/app.py` (branch `main`). In **Settings → Secrets** add `MOTHERDUCK_TOKEN`,
   `SKILLRADAR_MOTHERDUCK_DB = "skillradar"`, and `SKILLRADAR_SERVE_ONLY = "1"` (hides the in-app
   Refresh — refreshes come from the daily cron).

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
grounded Q&A via structured tool-use over the corpus), the **Streamlit Community Cloud deployment**
(bring-your-own-key AI), the **production data layer on MotherDuck** (no data in git) with
pipeline failure alerting, and an **analytics-engineering layer in dbt** — the Silver→Gold star
schema + Gold marts, declarative data-quality tests, and lineage docs.
Next: error tracking (Sentry) + an in-app pipeline-health panel; parallel/incremental ingestion
and more sources; semantic résumé→jobs matching; a weekly AI market brief.

### Adding a new source

The Clean-Architecture split makes this a small, contained change: add a value to
`JobSource` (`domain/models.py`), write a connector implementing the `JobSourceConnector`
port under `infrastructure/sources/`, register it in `build_registry` (`sources/registry.py`),
and add board entries to `data/sources.json`. The `Arbeitnow` aggregator connector is a
worked example (a single global feed rather than a per-company board).
