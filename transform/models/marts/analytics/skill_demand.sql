{{
    config(
        materialized='incremental',
        unique_key=['role', 'skill', 'category', 'snapshot_date'],
        incremental_strategy='delete+insert',
        alias='skill_demand'
    )
}}

-- GOLD leaderboard (the headline metric). Per role, count the DISTINCT postings (deduped by
-- content hash, via fact_job_posting) that require each skill, for one daily snapshot.
--
-- Reproduces domain/demand.py exactly: int_posting_roles is the deduped posting<->role bridge and
-- fact_job_skill is one row per (deduped posting, skill), so this is a plain grouped count. The
-- incremental delete+insert on (role, skill, category, snapshot_date) mirrors the Python
-- `replace_snapshot` — it replaces the current snapshot's rows and leaves prior days intact.
--
-- snapshot_date comes from the pipeline (`--vars snapshot_date=YYYY-MM-DD`) so dbt and the Python
-- fallback agree; ad-hoc `dbt build` defaults to dbt's run start date.

{% set snapshot_date = var('snapshot_date', run_started_at.strftime('%Y-%m-%d')) %}

with posting_roles as (
    select job_id, role from {{ ref('int_posting_roles') }}
),

posting_skills as (
    select job_id, skill, category from {{ ref('fact_job_skill') }}
)

select
    pr.role,
    ps.skill,
    ps.category,
    count(distinct pr.job_id)       as job_count,
    cast('{{ snapshot_date }}' as date) as snapshot_date
from posting_roles pr
join posting_skills ps
    on ps.job_id = pr.job_id
group by pr.role, ps.skill, ps.category
