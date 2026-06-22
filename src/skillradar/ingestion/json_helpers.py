"""Defensive accessors for loosely-typed ATS JSON payloads (parsed into dicts).

Port of the .NET ``JsonHelpers`` (SkillRadar.Ingestion/Json/JsonHelpers.cs)."""

from __future__ import annotations

from typing import Any


def get_str(obj: Any, key: str) -> str | None:
    if isinstance(obj, dict):
        value = obj.get(key)
        if isinstance(value, str):
            return value
    return None


def get_bool(obj: Any, key: str) -> bool:
    if isinstance(obj, dict):
        value = obj.get(key)
        if isinstance(value, bool):
            return value
    return False


def get_id(obj: Any, key: str) -> str | None:
    """Read a property as a raw id string, accepting either a JSON string or number."""
    if not isinstance(obj, dict) or key not in obj:
        return None
    value = obj[key]
    if isinstance(value, bool):  # bool is a subclass of int — exclude it
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return None


def get_child(obj: Any, key: str) -> dict | None:
    if isinstance(obj, dict):
        child = obj.get(key)
        if isinstance(child, dict):
            return child
    return None
