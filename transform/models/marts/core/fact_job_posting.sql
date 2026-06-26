-- Central fact: one row per ACTIVE posting, deduplicated cross-source by content hash (keep a
-- single representative per dedup_hash). Carries foreign keys to the company/date dimensions and
-- degenerate attributes (source, title, ...) used by the marts. `posting_count = 1` is the
-- additive measure. Because identical postings share a hash (same title/skills), keeping one
-- representative preserves every demand count.

with active as (
    select * from {{ ref('stg_jobs') }}
    where is_active
),

deduped as (
    select
        *,
        row_number() over (partition by dedup_hash order by job_id) as rn
    from active
)

select
    job_id,                                                       -- degenerate key (grain / PK)
    dedup_hash,
    {{ dbt_utils.generate_surrogate_key(['company']) }} as company_key,
    cast(coalesce(posted_at, first_seen_at) as date)    as posted_date_key,
    cast(first_seen_at as date)                         as first_seen_date_key,
    source,
    board_token,
    company,
    title,
    title_lower,
    location,
    is_remote,
    apply_url,
    posted_at,
    first_seen_at,
    last_seen_at,
    1 as posting_count
from deduped
where rn = 1
