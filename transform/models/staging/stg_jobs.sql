-- Cleaned, typed postings from the Silver `jobs` table. Drops the heavy `description` column
-- (Gold never needs it) and exposes `title_lower` for SQL role classification.

with source as (
    select * from {{ source('skillradar', 'jobs') }}
)

select
    job_id,
    source,
    source_job_id,
    board_token,
    company,
    title,
    lower(title)        as title_lower,
    location,
    is_remote,
    apply_url,
    posted_at,
    dedup_hash,
    first_seen_at,
    last_seen_at,
    is_active
from source
