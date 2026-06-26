-- GOLD trend table — every daily snapshot's per-role/skill counts, for the dashboard's
-- demand-over-time charts. It is exactly skill_demand minus the category column, so it can never
-- drift from the leaderboard. The full daily history flows through because skill_demand accumulates
-- one snapshot per run (incremental); rebuilding this projection each run stays cheap.

select
    role,
    skill,
    snapshot_date,
    job_count
from {{ ref('skill_demand') }}
