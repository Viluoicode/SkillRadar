# Reference — original .NET implementation (archived to a tag)

SkillRadar was first built as an **ASP.NET Core** app (ASP.NET Core 9 · EF Core/PostgreSQL ·
Hangfire · React/Redux SPA). That code was the source of truth for *product behavior* — the
Python implementation's parity tests (skill matcher/guards, dedup hashing, Gold aggregation,
connector parsing) were ported from it.

To keep this repository focused on the active Python product, the .NET sources were **removed from
`main` and preserved at the git tag [`dotnet-archive`](../../../tags)**. Recover them anytime with:

```bash
git checkout dotnet-archive -- reference/dotnet-original   # restore into the working tree
# or browse on GitHub at the dotnet-archive tag
```

The active, maintained implementation is the Python Data-Engineering pipeline at the repository
root (`src/skillradar/`, `dashboard/`, `tests/`). See the root [README.md](../README.md).
