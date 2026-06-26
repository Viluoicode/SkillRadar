-- Company dimension. One row per company that currently has active postings. first_seen/last_seen
-- (min/max over its postings) give it a slowly-changing flavour without a full SCD-2 history.

with postings as (
    select * from {{ ref('stg_jobs') }}
    where is_active
)

select
    {{ dbt_utils.generate_surrogate_key(['company']) }} as company_key,
    company,
    min(first_seen_at)          as first_seen_at,
    max(last_seen_at)           as last_seen_at,
    count(distinct dedup_hash)  as active_postings,
    count(distinct source)      as source_count
from postings
group by company
