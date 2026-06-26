-- Skill dimension. One row per skill (with its category from the skill dictionary) plus
-- first_seen/last_seen across the active postings that mention it.

with links as (
    select
        s.skill,
        s.category,
        j.job_id,
        j.first_seen_at,
        j.last_seen_at
    from {{ ref('stg_job_skills') }} s
    join {{ ref('stg_jobs') }} j
        on j.job_id = s.job_id
        and j.is_active
)

select
    {{ dbt_utils.generate_surrogate_key(['skill']) }} as skill_key,
    skill,
    min(category)               as category,
    count(distinct job_id)      as active_postings,
    min(first_seen_at)          as first_seen_at,
    max(last_seen_at)           as last_seen_at
from links
group by skill
