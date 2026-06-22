"""Target role families and the title patterns that classify a posting into each.

Ported from the .NET ``DbSeeder.DefaultRoles`` (patterns are matched case-insensitively
as substrings of the job title). Modeled for many; the MVP can focus on one."""

from __future__ import annotations

# (role name, lower-cased title patterns)
DEFAULT_ROLES: list[tuple[str, list[str]]] = [
    (
        "Backend Engineer",
        ["backend engineer", "back-end engineer", "backend developer", "backend software engineer"],
    ),
    (
        "Frontend Engineer",
        ["frontend engineer", "front-end engineer", "frontend developer", "ui engineer"],
    ),
    ("Full Stack Engineer", ["full stack", "fullstack", "full-stack engineer"]),
    ("Data Engineer", ["data engineer", "etl engineer", "analytics engineer"]),
    ("Data Scientist", ["data scientist", "machine learning scientist"]),
    ("Machine Learning Engineer", ["machine learning engineer", "ml engineer", "ai engineer"]),
    (
        "DevOps Engineer",
        ["devops", "site reliability", "sre", "platform engineer", "infrastructure engineer"],
    ),
    (
        "Mobile Engineer",
        ["mobile engineer", "ios engineer", "android engineer", "mobile developer"],
    ),
]
