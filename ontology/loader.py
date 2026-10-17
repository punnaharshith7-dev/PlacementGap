from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ontology.canonicalizer import SkillNode


def load_skills(path: Path | None = None) -> list[SkillNode]:
    source = path or Path(__file__).parent / "data" / "skills.yaml"
    content = yaml.safe_load(source.read_text(encoding="utf-8"))
    return [SkillNode.model_validate(row) for row in content.get("skills", [])]


def load_prerequisites(path: Path | None = None) -> dict[str, list[str]]:
    source = path or Path(__file__).parent / "data" / "prereqs.yaml"
    content = yaml.safe_load(source.read_text(encoding="utf-8"))
    return {key: list(value) for key, value in content.get("prerequisites", {}).items()}


def load_edges(path: Path | None = None) -> dict[str, dict[str, Any]]:
    source = path or Path(__file__).parent / "data" / "prereqs.yaml"
    content = yaml.safe_load(source.read_text(encoding="utf-8"))
    return {edge: dict(content.get(edge, {})) for edge in ("prerequisites", "adjacent", "specializes")}
