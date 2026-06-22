"""Domain layer — pure business types and rules.

Modules here must not import I/O libraries (``duckdb``, ``httpx``, ``pandas``) or any
other SkillRadar layer. They depend only on the standard library and ``pydantic``. This
keeps the core skill-matching, dedup and aggregation rules fast and trivially testable.
"""
