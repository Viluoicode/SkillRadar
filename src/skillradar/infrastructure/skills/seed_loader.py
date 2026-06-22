"""Load the canonical skill dictionary from data/skills.seed.json (implements
``SkillCatalog``). Each skill gets a stable 1-based id by document order."""

from __future__ import annotations

import json
from pathlib import Path

from skillradar.domain.skills.dictionary import Skill


class JsonSkillCatalog:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> list[Skill]:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        skills: list[Skill] = []
        for i, item in enumerate(data.get("skills", []), start=1):
            skills.append(
                Skill(
                    skill_id=i,
                    name=item["name"],
                    category=item.get("category", ""),
                    aliases=tuple(item.get("aliases", [])),
                )
            )
        return skills
