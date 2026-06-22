# SkillRadar (Python) — Session Handoff

> **Purpose of this file:** a complete, self-contained brief so a *fresh* Claude session can
> pick up this project and continue with full context. Read this top-to-bottom first. It
> covers the product, both implementations, every decision, the architecture, the file map,
> what's done/verified, known gotchas, and the next steps.
>
> **Language note:** user communicates in Vietnamese; technical doc below is English with VN notes.

---

## 1. What this project is

**SkillRadar** = a **read-only job-market intelligence tool**. It aggregates real tech job
postings from *public ATS feeds*, extracts the skills each posting requires, and shows
**which skills are in demand per role family** + a filterable job list (every posting links to
its original "apply" page). It is an **analytics layer over public job data** — NOT a job board,
NOT a marketplace, no logins, no employer onboarding.

Goal for the user: a **Python Data-Engineering portfolio piece** (Medallion pipeline, DuckDB,
orchestration, dashboard) that delivers real value to anonymous visitors the moment it's deployed.

**Data sources (legal, tiered):**
- **Tier 1 — public ATS APIs (used):** Greenhouse, Lever, Ashby. Free JSON, fully legit.
- **Tier 2 — aggregator APIs (optional, not yet added):** Adzuna, RemoteOK, WeWorkRemotely, etc.
- **Tier 3 — NEVER scrape:** ITviec / TopCV / VietnamWorks (no public API → ToS/legal risk).
  VN on-site jobs are intentionally **out of scope**.

---

## 2. Two implementations in this repo

The repo root is `d:\DNTU\Tự Học\A job-market intelligence\` (NOT a git repo yet).

1. **.NET version (REFERENCE, untouched, original):** `src/SkillRadar.*`, `web/` (React SPA),
   `tests/`, `data/`. ASP.NET Core + EF Core/PostgreSQL + Hangfire + React/Redux/Recharts.
   This is the source of truth for *product behavior*. We did **not** modify it.
2. **Python version (NEW, the active work):** lives in the subfolder **`python/`**. This is what
   we built this session and what future work continues. Same product, modern DE stack.

The Python project **reuses** the two language-agnostic data assets, copied from the .NET
`data/` into `python/data/`:
- `sources.json` — 12 curated ATS boards (Greenhouse/Lever/Ashby + company slugs).
- `skills.seed.json` — ~150 skills with `name` / `category` / `aliases`.

---

## 3. Decisions already made (do not re-litigate)

Confirmed by the user via explicit Q&A:
1. **Serving:** **Streamlit only** (reads Gold/DuckDB directly). The React SPA is NOT carried over.
2. **Orchestration:** plain Python functions first → wrapped in a **Prefect** flow. (Airflow rejected.)
3. **Location:** Python lives **inside** `A job-market intelligence/python/` (a self-contained
   subfolder). .NET kept intact. *(User changed mind from the original "separate sibling folder".)*
4. **Skill extraction:** **port the proven regex matcher + guards** from .NET (NOT spaCy) — exact
   parity, no model downloads, fast in CI.

The original detailed plan file lives at:
`C:\Users\tranv\.claude\plans\skillradar-detailed-gleaming-kazoo.md`

---

## 4. Architecture (Medallion in Python)

```
Greenhouse · Lever · Ashby                (public ATS APIs)
        │  httpx + tenacity (retry/backoff, per-board isolation, polite delay)
        ▼
BRONZE   python/data/bronze/run_*.parquet     raw payloads exactly as fetched (replayable)
        │  pydantic + normalize + dedup + lifecycle
        ▼
SILVER   DuckDB: jobs, job_skills             typed, deduped (cross-source content hash),
        │                                     first/last_seen + is_active lifecycle
        │  regex skill matcher + guards, pandas/SQL aggregation
        ▼
GOLD     DuckDB: skill_demand, skill_trends   in-demand skills per role per snapshot; trends
        ▼
SERVING  Streamlit dashboard (reads Gold directly from DuckDB)

ORCHESTRATION: plain functions (pipeline/run.py) OR Prefect flow (pipeline/flow.py)
SCHEDULE/CI:   GitHub Actions — pipeline.yml (daily cron) + ci.yml (ruff + pytest)
```

**Storage choice:** Bronze = Parquet files on disk; Silver/Gold/meta = one embedded **DuckDB**
file (`python/data/skillradar.duckdb`). Zero-cost deploy: GitHub Actions runs the pipeline daily,
commits the refreshed DuckDB + Parquet; Streamlit Community Cloud serves the dashboard from it.

---

## 5. Tech stack

| Concern | Tool |
| --- | --- |
| Ingestion / resilience | `httpx` + `tenacity` |
| Validation | `pydantic` v2 |
| Transform + storage | `pandas` + **DuckDB** + Parquet (`pyarrow`); `pytz` for TIMESTAMPTZ reads |
| Skill extraction | stdlib `re` regex matcher + ambiguous-term guards (ported from .NET) |
| Orchestration | plain Python → **Prefect** (optional extra) |
| Schedule / CI | GitHub Actions |
| Dashboard | **Streamlit** + Altair |
| Quality | `ruff` (lint), `pytest` (tests), stdlib `logging` |
| Env/pkg | `uv` (preferred) or pip; `pyproject.toml` (hatchling, src layout) |

Python **3.12+** required (uses PEP 695 generics `def f[T](...)` and `enum.StrEnum`).

---

## 6. File map (everything under `python/`)

```
python/
├── pyproject.toml              # deps, ruff (line-length 100), pytest (pythonpath=src)
├── README.md                   # user-facing run/deploy docs
├── HANDOFF.md                  # THIS FILE
├── .gitignore                  # ignores .venv, *.duckdb, data/bronze/*.parquet (CI force-adds them)
├── m0_spike.py                 # M0: pull one Greenhouse board, print titles
├── src/skillradar/
│   ├── common/
│   │   ├── config.py           # Config dataclass; paths default to data/, overridable via SKILLRADAR_* env
│   │   ├── logging.py          # get_logger (stdlib)
│   │   ├── models.py           # JobSource(StrEnum: greenhouse/lever/ashby), FetchedJob (pydantic)
│   │   ├── text.py             # strip_html, normalize_for_key  (port of TextNormalizer.cs)
│   │   ├── dedup.py            # compute_dedup_hash (SHA256, port of DedupHasher.cs), make_job_id
│   │   ├── dates.py            # parse_iso, from_epoch_ms
│   │   ├── http.py             # build_client(), fetch_with_retry[T] (tenacity; retries 5xx+transport, NOT 4xx)
│   │   └── db.py               # connect(), ensure_schema() — all DuckDB DDL lives here
│   ├── ingestion/
│   │   ├── base.py             # JobSourceConnector Protocol, BoardConfig dataclass
│   │   ├── json_helpers.py     # get_str/get_bool/get_id/get_child (defensive dict access)
│   │   ├── greenhouse.py       # GreenhouseConnector  (boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true)
│   │   ├── lever.py            # LeverConnector       (api.lever.co/v0/postings/{t}?mode=json)
│   │   ├── ashby.py            # AshbyConnector       (api.ashbyhq.com/posting-api/job-board/{t}?includeCompensation=true)
│   │   ├── catalog.py          # load_catalog() — reads sources.json → list[BoardConfig]
│   │   └── registry.py         # build_registry(client); fetch_all_boards() = per-board isolation + delay + retry
│   ├── bronze/land.py          # land_bronze() → data/bronze/run_{run_id}.parquet
│   ├── silver/normalize.py     # upsert_jobs() — THE core Silver logic (see §8)
│   ├── skills/
│   │   ├── guards.py           # SkillGuard + DEFAULT_GUARDS (C / R / Go false-positive rejection)
│   │   ├── matcher.py          # SkillTerms, SkillMatcher (port of SkillMatcher.cs regex+boundaries)
│   │   ├── dictionary.py       # Skill dataclass, load_skills(), build_matcher()
│   │   └── extract.py          # extract_job_skills() → writes job_skills (incremental or replace_all)
│   ├── gold/
│   │   ├── roles.py            # DEFAULT_ROLES: 8 role families + lower-cased title patterns
│   │   └── aggregate.py        # aggregate_skill_demand() → skill_demand + skill_trends (cross-source dedup)
│   └── pipeline/
│       ├── run.py              # run_pipeline() plain orchestration + _record_run + main() (CLI entry)
│       └── flow.py             # Prefect flow (reuses run.py's step fns + _record_run/_status)
├── dashboard/app.py            # Streamlit: stats header, top-skills bar chart, filterable paginated job list
├── data/
│   ├── sources.json            # copied from .NET (12 boards)
│   ├── skills.seed.json        # copied from .NET (~150 skills)
│   ├── bronze/ , gold/         # output dirs
│   └── skillradar.duckdb       # generated by a run (gitignored)
├── tests/
│   ├── test_dedup.py           # port of DedupHasherTests
│   ├── test_matcher.py         # port of SkillMatcherTests (boundaries + C/R/Go guards)
│   ├── test_connectors.py      # port of ConnectorTests (httpx.MockTransport)
│   └── test_pipeline.py        # Silver+Gold: extraction, demand aggregation, cross-source dedup, lifecycle
└── .github/workflows/
    ├── ci.yml                  # ruff + pytest
    └── pipeline.yml            # daily cron: run pipeline, commit refreshed data
```

---

## 7. Data model (DuckDB tables — defined in `common/db.py`)

- **`jobs`** (Silver, one row per posting): `job_id` (PK = sha256(source|source_job_id)), `source`,
  `source_job_id`, `board_token`, `company`, `title`, `location`, `is_remote`, `description`,
  `apply_url`, `posted_at` (TIMESTAMPTZ), `dedup_hash`, `first_seen_at`, `last_seen_at`, `is_active`.
- **`job_skills`** (Silver): `job_id`, `skill` (canonical name), `category`.
- **`skill_demand`** (Gold): `role`, `skill`, `category`, `job_count`, `snapshot_date` (DATE).
- **`skill_trends`** (Gold): `role`, `skill`, `snapshot_date`, `job_count` (accumulates daily).
- **`ingestion_runs`** (meta): `run_id` (PK), `trigger`, `started_at`, `finished_at`, `status`,
  `boards_attempted`, `boards_succeeded`, `raw_fetched`, `jobs_upserted`, `jobs_deactivated`, `errors`.

---

## 8. Key behaviors ported from .NET (preserve these — they have parity tests)

- **Dedup hash** (`common/dedup.py`): `SHA256(normalize(company)|normalize(title)|normalize(location))`,
  uppercase hex. `normalize_for_key` = lower + strip non-alnum + collapse whitespace.
- **Cross-source dedup** (`silver/normalize.py`): a brand-new posting whose `dedup_hash` is already
  owned by an *active* job from a **different source** is skipped. The owner map updates as we go
  (so two identical postings from different sources in one run → only the first is kept).
- **Lifecycle** (`silver/normalize.py`): `first_seen_at` set on insert; `last_seen_at`+`is_active=True`
  on every touch. A job is **deactivated only if its board fetched successfully this run** but the job
  vanished. A failed board NEVER deactivates its jobs (`succeeded_boards` set gates this).
- **Per-board isolation** (`ingestion/registry.py`): one board's exception is logged and skipped; the
  run continues. Run status = `succeeded` / `completed_with_errors` (some ok) / `failed` (none ok).
- **Skill matcher** (`skills/matcher.py`): single case-insensitive regex; boundary class is
  `[A-Za-z0-9+#]` (NOT `.`), so `C#`/`.NET`/`C++`/`Node.js` match, `JS`∉`JSON`, `Go`∉`Google`, and a
  trailing sentence period still matches. Longer terms first → `GitHub Actions` beats `GitHub`,
  `Node.js` beats `Node`. Returns distinct skill ids.
- **Guards** (`skills/guards.py`): reject ambiguous matches by surrounding context — `C` (C-level,
  C-suite, Series C, D.C.), `R` (R&D, R$), `Go` (Go-to-Market, Go-live, "as you go"). A skill is still
  recorded if *another* occurrence passes.
- **Role classification + demand** (`gold/aggregate.py`): over **active** jobs deduped by content hash,
  a job matches a role if its lower-cased title contains any of that role's patterns; count distinct
  skills per matching job. Today's snapshot is replaced each run; `skill_trends` accumulates.

8 roles in `gold/roles.py`: Backend, Frontend, Full Stack, Data Engineer, Data Scientist, ML Engineer,
DevOps, Mobile.

---

## 9. Status — what's DONE and VERIFIED

**Milestones M0–M6 complete.** Verified this session by actually running it:
- `ruff check` clean; **`pytest` = 49 passed** (parity tests for matcher/guards/dedup/connectors/pipeline).
- **Full live run**: `python -m skillradar.pipeline.run` → 11/12 boards ok (`lever/ramp` returned 404,
  gracefully isolated → status `completed_with_errors`), **2740 jobs**, 10550 skill links, **302 demand rows**.
  Data Engineer top skills came out as SQL, Python, Spark, Airflow, ETL, Scala — sensible.
- Dashboard SQL (stats, demand, `string_agg` job list with filters + apply links) validated against the live DB.
- M0 spike pulled 512 real Stripe jobs.

`skill_trends` is already being written each run, so the M7 trend chart just needs a UI addition.

---

## 10. How to run / verify (Windows, PowerShell)

`uv` was NOT installed on this machine; Python 3.14.2 is present as `py`/`python`. Two options:

```powershell
# Option A — uv (preferred once installed)
cd "d:\DNTU\Tự Học\A job-market intelligence\python"
uv venv ; uv pip install -e ".[dev]"
uv run python -m skillradar.pipeline.run      # Bronze→Silver→Gold → data/skillradar.duckdb
uv run streamlit run dashboard/app.py
uv run pytest ; uv run ruff check .

# Option B — venv + pip (what was used this session; .venv already exists in python/)
.\.venv\Scripts\python.exe -m pip install httpx tenacity "pydantic>=2.6" pandas duckdb pyarrow pytz pytest ruff
$env:PYTHONPATH = "$PWD\src"                   # tests use pythonpath=src; the runner needs it on PYTHONPATH
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m skillradar.pipeline.run --trigger verify
```

Inspect results:
```powershell
.\.venv\Scripts\python.exe -c "import duckdb;print(duckdb.connect(r'data\skillradar.duckdb',read_only=True).execute(\"SELECT role,skill,job_count FROM skill_demand ORDER BY job_count DESC LIMIT 20\").df())"
```

---

## 11. Known gotchas / notes for the next session

- **`pytz` is required**: pandas 3.0 dropped it, but DuckDB needs it to materialize TIMESTAMPTZ to
  Python (`.fetchone()` on a tz column fails without it). It's in `pyproject.toml` deps. The app/pipeline
  use `.df()` (Arrow path) which is more tolerant, but keep pytz installed.
- **Running the module**: there is no editable install in the existing `.venv`, so set
  `PYTHONPATH=…/python/src` before `python -m skillradar.pipeline.run`. `uv pip install -e .` removes this need.
- **GitHub workflows assume `python/` is the repo root.** If the whole `A job-market intelligence`
  becomes one git repo, move `.github/workflows/*` to the repo root and add `working-directory: python`
  to each run step. The repo is currently NOT git-initialized.
- **Stderr noise in PowerShell**: pipeline logs go to stderr; PowerShell wraps them as
  "NativeCommandError" — this is cosmetic, not a failure. Check the final summary line / exit code.
- **Silver writes by full table rewrite** (`DELETE` + `INSERT … SELECT * FROM jobs_df`) to preserve the
  DDL schema. Fine at single-machine scale (thousands of rows); revisit if volume grows large.
- **`sources.json` has only 12 boards** (one, `lever/ramp`, currently 404s). The MVP "Definition of
  Done" wants **≥30 ATS companies + 1 aggregator** — see next steps.

---

## 12. Next steps (recommended order)

1. **Hit the DoD**: expand `data/sources.json` toward ~30 working ATS boards (verify each slug returns
   200), and add **one Tier-2 aggregator** connector (e.g. RemoteOK/Arbeitnow — no key — or Adzuna with a
   free key). New connector = implement the `JobSourceConnector` protocol + register it in
   `ingestion/registry.py` + add a `JobSource` enum value + handle it in `catalog.py`.
2. **M7 — Trends chart**: `skill_trends` is already populated; add a Streamlit line chart (skill demand
   over `snapshot_date`) per role. (Needs several days of snapshots to be interesting.)
3. **M8 — Skill-gap (optional)**: a text input for the user's skills → show in-demand skills they're
   missing for a chosen role; optional LLM learning roadmap (use the `openai` SDK / Anthropic, force JSON,
   validate with pydantic, cache results).
4. **M9 — Deploy**: git-init, push to GitHub, enable the cron workflow, deploy `dashboard/app.py` to
   Streamlit Community Cloud, finish README with screenshots + a short demo clip.
5. **Stretch (DE resume boosters)**: introduce **dbt** for the Silver→Gold SQL transforms; consider Polars.

---

## 13. Quick orientation checklist for a fresh session

- Read this file, then skim `python/README.md` and the plan at
  `C:\Users\tranv\.claude\plans\skillradar-detailed-gleaming-kazoo.md`.
- The .NET code in the parent folders is **reference only** — mine it for behavior, don't change it.
- Run `pytest` first to confirm the environment, then a live `pipeline.run`.
- All pipeline logic is plain functions in `src/skillradar/*`; `pipeline/run.py` wires them in order
  Bronze → Silver → Gold; `pipeline/flow.py` is the Prefect mirror.
