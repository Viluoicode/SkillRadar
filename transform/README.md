# `transform/` — the dbt analytics-engineering layer (Silver → Gold)

This dbt project owns SkillRadar's **Silver → Gold** transform. The Python pipeline handles
**Bronze → Silver** (HTTP fetch, validation, dedup, lifecycle, regex skill extraction) and writes
the `jobs` / `job_skills` Silver tables; dbt models the warehouse from there: a conformed
**star schema** plus the Gold marts the dashboard serves.

```
sources (Silver)          staging            marts/core (star schema)        marts/analytics (Gold)
  jobs ───────────────►  stg_jobs ─────┬──►  dim_company  dim_skill  dim_role   skill_demand (incremental)
  job_skills ─────────►  stg_job_skills │     dim_date                          skill_trends
  seed_roles (seed) ────────────────────┴──►  fact_job_posting ──► fact_job_skill ─┘
                                              (+ int_posting_roles bridge)
```

- **`fact_job_posting`** — grain: one active, hash-deduped posting; FKs to `dim_company` / `dim_date`.
- **`fact_job_skill`** — bridge grain: posting × skill; FKs to `dim_skill` / `fact_job_posting`.
- **`skill_demand`** — Gold leaderboard (distinct postings per role requiring each skill, per daily
  snapshot). Aliased to the table name the dashboard already reads, so the serving layer is
  untouched. Reproduces `domain/demand.py` exactly (guarded by `tests/test_dbt_parity.py`).
- **`skill_trends`** — `skill_demand` projected to `(role, skill, snapshot_date, job_count)`.

## Run it

dbt-core has no Python 3.14 wheels yet, so it lives in its own env. From the repo root:

```bash
pip install "dbt-duckdb>=1.9"        # or:  pip install -e ".[dbt]"

dbt deps  --project-dir transform --profiles-dir transform
dbt build --project-dir transform --profiles-dir transform --target dev      # build + test
dbt build --project-dir transform --profiles-dir transform --target dev --full-refresh   # first cutover run

# lineage docs (the DAG screenshot)
dbt docs generate --project-dir transform --profiles-dir transform
dbt docs serve    --project-dir transform --profiles-dir transform
```

In normal use you don't call dbt by hand — the pipeline does: `skillradar --gold dbt` runs
Bronze→Silver in Python, then `dbt build` for Gold. See [`.claude/docs/dbt_transform.md`](../.claude/docs/dbt_transform.md).

## Targets

`profiles.yml` mirrors the app's `config.data_target`:

| Target | Warehouse | Selected when |
| --- | --- | --- |
| `dev` (default) | local DuckDB file (`SKILLRADAR_DUCKDB`, default `../data/skillradar.duckdb`) | no `MOTHERDUCK_TOKEN` |
| `prod` | MotherDuck `md:$SKILLRADAR_MOTHERDUCK_DB` | `MOTHERDUCK_TOKEN` set |

## Tests

`dbt build` runs every model **and** its tests: `not_null` / `unique` on dim keys, `relationships`
fact→dim, `accepted_values` on `source` / `role` / skill `category`, and uniqueness on the mart
grains. Source **freshness** on `jobs.last_seen_at` runs separately:
`dbt source freshness --project-dir transform --profiles-dir transform`.
