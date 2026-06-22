# Reference — original .NET implementation (archived)

This folder holds the **original ASP.NET Core implementation** of SkillRadar
(`dotnet-original/`). It is kept **for reference only**:

- It is the source of truth for *product behavior* — the Python implementation's parity
  tests (skill matcher/guards, dedup hashing, Gold aggregation, connector parsing) were
  ported from here.
- It demonstrates the same product built on a classic enterprise stack
  (ASP.NET Core 9 · EF Core/PostgreSQL · Hangfire · React/Redux/Recharts SPA).

**It is not part of the active product and is not built or tested in CI.** The active,
maintained implementation is the Python Data-Engineering pipeline at the repository root
(`src/skillradar/`, `dashboard/`, `tests/`). See the root `README.md`.

To explore the .NET solution:

```bash
cd reference/dotnet-original
dotnet build SkillRadar.slnx     # requires .NET 9 SDK + PostgreSQL (see dotnet-original/README.md)
```
