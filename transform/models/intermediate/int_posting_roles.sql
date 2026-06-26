-- Posting <-> role bridge (the M:N between fact_job_posting and dim_role). A deduped posting
-- belongs to a role when its lower-cased title CONTAINS any of the role's seed patterns; a posting
-- can match several roles. Mirrors the substring matching in domain/demand.py / domain/roles.py.

select distinct
    p.job_id,
    r.role
from {{ ref('fact_job_posting') }} p
join {{ ref('seed_roles') }} r
    on p.title_lower like '%' || r.pattern || '%'
