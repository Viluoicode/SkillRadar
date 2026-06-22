"""Load the curated board list from data/sources.json (implements ``BoardCatalog``)."""

from __future__ import annotations

import json
from pathlib import Path

from skillradar.application.dto import BoardConfig
from skillradar.domain.models import JobSource


class JsonBoardCatalog:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> list[BoardConfig]:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        boards: list[BoardConfig] = []
        for entry in data.get("boards", []):
            raw_source = str(entry.get("source", "")).strip().lower()
            try:
                source = JobSource(raw_source)
            except ValueError:
                # Unknown source in the catalog — skip rather than break the run.
                continue
            token = entry.get("token")
            if not token:
                continue
            boards.append(BoardConfig(source=source, token=token, company=entry.get("company")))
        return boards
