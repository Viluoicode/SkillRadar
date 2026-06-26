-- Conformed date dimension: a contiguous daily spine spanning every posting/seen date in the
-- warehouse (plus a small buffer through today), so every *_date_key on the facts resolves here.

with bounds as (
    select
        cast(least(
            min(first_seen_at),
            coalesce(min(posted_at), min(first_seen_at))
        ) as date) as start_date,
        cast(greatest(
            max(last_seen_at),
            coalesce(max(posted_at), max(last_seen_at)),
            current_timestamp
        ) as date) + interval 2 day as end_date
    from {{ ref('stg_jobs') }}
),

spine as (
    select unnest(generate_series(
        (select cast(start_date as timestamp) from bounds),
        (select cast(end_date   as timestamp) from bounds),
        interval 1 day
    )) as date_day
)

select
    cast(date_day as date)               as date_key,
    extract(year   from date_day)        as year,
    extract(month  from date_day)        as month,
    extract(day    from date_day)        as day,
    extract(isodow from date_day)        as iso_day_of_week,  -- 1 = Mon .. 7 = Sun
    strftime(date_day, '%Y-%m')          as year_month,
    extract(isodow from date_day) >= 6   as is_weekend
from spine
