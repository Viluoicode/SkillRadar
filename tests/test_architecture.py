"""Enforce the Clean Architecture dependency rule by scanning source imports.

Inner layers must not depend on outer layers or on I/O technologies:
* ``domain`` may import only the stdlib + pydantic — never another SkillRadar layer.
* ``application`` may import ``domain`` — never ``infrastructure`` / ``interface``.
* Neither ``domain`` nor ``application`` may import duckdb / httpx / pandas / streamlit /
  altair / prefect / pyarrow (those live behind ports in ``infrastructure``).

A lightweight regex scan keeps this dependency-free (no import-linter needed) and fast.
"""

from __future__ import annotations

import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "skillradar"

_IO_LIBS = ("duckdb", "httpx", "pandas", "streamlit", "altair", "prefect", "pyarrow")
_IMPORT = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z0-9_.]+)", re.MULTILINE)


def _imported_modules(path: Path) -> list[str]:
    return _IMPORT.findall(path.read_text(encoding="utf-8"))


def _modules_in(layer: str) -> list[Path]:
    return sorted((PKG / layer).rglob("*.py"))


def test_domain_imports_only_stdlib_and_pydantic():
    forbidden = {"skillradar.application", "skillradar.infrastructure", "skillradar.interface"}
    for path in _modules_in("domain"):
        for mod in _imported_modules(path):
            assert mod.split(".")[0] not in _IO_LIBS, f"{path.name} imports I/O lib: {mod}"
            assert not any(mod.startswith(f) for f in forbidden), f"{path.name} -> {mod}"


def test_application_does_not_depend_on_outer_layers_or_io():
    forbidden = {"skillradar.infrastructure", "skillradar.interface"}
    for path in _modules_in("application"):
        for mod in _imported_modules(path):
            assert mod.split(".")[0] not in _IO_LIBS, f"{path.name} imports I/O lib: {mod}"
            assert not any(mod.startswith(f) for f in forbidden), f"{path.name} -> {mod}"
