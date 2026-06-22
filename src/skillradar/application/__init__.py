"""Application layer — use-cases and the ports they depend on.

Modules here orchestrate the domain rules through abstract ports (protocols). They depend
only on :mod:`skillradar.domain` and never on a concrete I/O technology (DuckDB, httpx,
pandas) — those live behind the ports and are wired in at the composition root."""
