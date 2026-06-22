# SkillRadar

A read-only **job-market intelligence** tool. SkillRadar aggregates real tech job postings
from public ATS feeds (**Greenhouse, Lever, Ashby**), runs a Medallion data pipeline to ingest →
normalize → dedupe, extracts required skills with a rule-based dictionary, and presents a
dashboard of in-demand skills per target role plus a filterable job list. Every posting links
out to the original source so you apply directly there.

## Stack

- **Backend:** ASP.NET Core 9 Web API, EF Core, PostgreSQL
- **Pipeline scheduling:** Hangfire (durable jobs, retries, dashboard) on PostgreSQL storage
- **Frontend:** React + Vite + TypeScript SPA (Recharts for the skill chart)

## Architecture

A Medallion (Bronze/Silver/Gold) data model:

| Layer  | Tables | Purpose |
| ------ | ------ | ------- |
| Bronze | `raw_job_postings` | Immutable raw payloads as fetched (replayable/debuggable) |
| Silver | `jobs` | Normalized, deduplicated postings with `first/last_seen` + `is_active` lifecycle |
| Gold   | `skills`, `skill_aliases`, `job_skills`, `skill_demand`, `roles` | Extracted skills + demand aggregates |
| Meta   | `ingestion_runs` | Per-run observability (counts, per-source errors) |

**Pipeline** (`SkillRadar.Ingestion`): for each curated board it fetches via a resilient typed
`HttpClient` (Polly retry/backoff + per-source isolation), stores raw payloads (Bronze),
upserts canonical jobs with composite dedup (Silver), then extracts skills and aggregates demand
(Gold). A failing board is logged and skipped without aborting the run, and a board's jobs are
only deactivated when that board fetched successfully.

### Projects
- `src/SkillRadar.Core` — domain entities, skill matcher, dedup/text utilities, connector contracts
- `src/SkillRadar.Data` — EF Core `DbContext`, migrations, seeding
- `src/SkillRadar.Ingestion` — ATS connectors + pipeline + Hangfire job
- `src/SkillRadar.Api` — Web API endpoints, Hangfire host, startup migration + seeding
- `web/` — React SPA
- `tests/SkillRadar.Tests` — xUnit (connectors mocked, dedup, skill extraction, pipeline)
- `data/` — `sources.json` (curated board list) and `skills.seed.json` (skill dictionary)

## Prerequisites

- .NET SDK 9 (pinned via `global.json`)
- Node.js 20+
- PostgreSQL 16 (a Docker container is the simplest path)

## Setup

### 1. Database

```bash
docker run -d --name skillradar-pg \
  -e POSTGRES_PASSWORD=skillradar -e POSTGRES_USER=skillradar -e POSTGRES_DB=skillradar \
  -p 5433:5432 postgres:16
```

The default connection string (`appsettings.json` / `SKILLRADAR_CONNECTION`) targets
`localhost:5433`. Migrations and seeding run automatically on API startup.

To target a different database, set the connection string via environment variable:

```bash
# PowerShell
$env:SKILLRADAR_CONNECTION = "Host=localhost;Port=5432;Database=skillradar;Username=...;Password=..."
```

### 2. API

```bash
dotnet run --project src/SkillRadar.Api
```

- API + Hangfire dashboard listen on `http://localhost:5038`
- Hangfire dashboard: `http://localhost:5038/hangfire`
- The recurring ingestion job runs on the `Ingestion:Cron` schedule (hourly by default)

### 3. SPA

```bash
cd web
npm install
npm run dev          # http://localhost:5173 (proxies /api to :5038)
```

Click **Refresh data** in the UI (or `POST /api/ingest`) to ingest postings, then explore the
dashboard and jobs list.

## API endpoints

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET  | `/api/roles` | Seeded target roles |
| GET  | `/api/skill-demand?role={id}&top={n}` | Top in-demand skills for a role (latest snapshot) |
| GET  | `/api/jobs?skill=&source=&company=&location=&remote=&postedAfter=&search=&page=&pageSize=` | Filterable, paginated active jobs |
| GET  | `/api/stats` | Totals + last run status |
| POST | `/api/ingest` | Enqueue an on-demand ingestion run (Hangfire) |

## Configuration (`appsettings.json`)

```jsonc
"Ingestion": {
  "SourcesPath": "../../data/sources.json",   // curated board tokens
  "SkillsSeedPath": "../../data/skills.seed.json",
  "DelayBetweenBoardsMs": 500,                 // polite delay between board calls
  "Cron": "0 * * * *"                          // recurring ingestion schedule
},
"Cors": { "Origins": [ "http://localhost:5173" ] }
```

Add or remove companies by editing `data/sources.json` (source + board token). Extend the skill
dictionary via `data/skills.seed.json`; new entries are loaded on next startup.

## Tests

```bash
dotnet test
```

## Deferred (future phases)

Skill-gap analysis (your skills vs. demand), time-trend charts (snapshots are already captured
via `skill_demand.snapshot_date`), aggregator-API sources, multi-role comparison, and an admin
UI for managing sources/skills.
