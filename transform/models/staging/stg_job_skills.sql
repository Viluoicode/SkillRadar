-- Distinct (job_id, skill) skill links with a single, deterministic category per pair.
-- Mirrors the Python aggregation's `drop_duplicates(["job_id", "skill"])` (first category wins);
-- here we pick the category deterministically so dbt is reproducible. In practice a skill maps to
-- exactly one category (from the skill dictionary), so this only guards a degenerate case.

with source as (
    select
        job_id,
        skill,
        category
    from {{ source('skillradar', 'job_skills') }}
),

deduped as (
    select
        job_id,
        skill,
        category,
        row_number() over (
            partition by job_id, skill
            order by category nulls last
        ) as rn
    from source
)

select
    job_id,
    skill,
    category
from deduped
where rn = 1
