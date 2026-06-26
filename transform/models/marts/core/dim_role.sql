-- Role dimension — the target role families, conformed from the seed. The title patterns that
-- map postings to roles live in seed_roles (and are applied in the posting<->role bridge).

with roles as (
    select distinct role from {{ ref('seed_roles') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['role']) }} as role_key,
    role
from roles
