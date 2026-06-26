-- Bridge fact for the posting <-> skill many-to-many. Grain: one row per (deduped posting, skill).
-- This is what the demand mart counts. Carries the skill/category as degenerate attributes (so the
-- mart matches the Python aggregation's per-(job, skill) category exactly) plus FKs to the dims.

with postings as (
    select
        job_id,
        dedup_hash,
        company_key,
        posted_date_key
    from {{ ref('fact_job_posting') }}
),

skills as (
    select
        job_id,
        skill,
        category
    from {{ ref('stg_job_skills') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['p.job_id', 's.skill']) }} as job_skill_key,
    p.job_id,
    p.dedup_hash,
    {{ dbt_utils.generate_surrogate_key(['s.skill']) }}            as skill_key,
    s.skill,
    s.category,
    p.company_key,
    p.posted_date_key
from postings p
join skills s
    on s.job_id = p.job_id
