from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class SkillNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    canonical_name: str
    category: str
    aliases: list[str] = Field(default_factory=list)
    description: str
    market_demand_weight: float = Field(ge=0, le=1)


class CanonicalMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill_id: str | None
    canonical_name: str | None
    confidence: float = Field(ge=0, le=1)
    method: str
    raw_text: str


def normalize_alias(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


class Canonicalizer:
    def __init__(
        self,
        skills: list[SkillNode],
        *,
        extra_aliases: dict[str, str] | None = None,
        threshold: float = 0.82,
        nearest_neighbor: Callable[[str, list[SkillNode]], tuple[str, float] | None] | None = None,
    ) -> None:
        self.skills = {skill.id: skill for skill in skills}
        self.threshold = threshold
        self.nearest_neighbor = nearest_neighbor or self._ngram_neighbor
        self._canonical: dict[str, SkillNode] = {}
        self._aliases: dict[str, SkillNode] = {}
        for skill in skills:
            self._canonical[normalize_alias(skill.canonical_name)] = skill
        # Canonical names always win over ambiguous aliases.
        for skill in skills:
            for alias in skill.aliases:
                self._aliases.setdefault(normalize_alias(alias), skill)
        for alias, skill_id in (extra_aliases or {}).items():
            if skill_id in self.skills:
                self._aliases[normalize_alias(alias)] = self.skills[skill_id]

    @classmethod
    def from_default(cls) -> Canonicalizer:
        root = Path(__file__).parent / "data"
        return cls.from_files(root / "skills.yaml", root / "aliases.yaml")

    @classmethod
    def from_files(cls, skills_path: Path, aliases_path: Path) -> Canonicalizer:
        skills_data = yaml.safe_load(skills_path.read_text(encoding="utf-8"))
        aliases_data = yaml.safe_load(aliases_path.read_text(encoding="utf-8"))
        skills = [SkillNode.model_validate(row) for row in skills_data.get("skills", [])]
        aliases = aliases_data.get("aliases", {})
        return cls(skills, extra_aliases=aliases)

    def canonicalize(self, text: str, context: str | None = None) -> CanonicalMatch:
        raw = text.strip()
        normalized = normalize_alias(raw)
        exact = self._canonical.get(normalized)
        if exact:
            return CanonicalMatch(
                skill_id=exact.id,
                canonical_name=exact.canonical_name,
                confidence=1.0,
                method="exact",
                raw_text=raw,
            )
        if os.getenv("PLACEMENTGAP_ABLATION") == "no_ontology":
            return CanonicalMatch(
                skill_id=None,
                canonical_name=None,
                confidence=0,
                method="UNRESOLVED",
                raw_text=raw,
            )
        alias = self._aliases.get(normalized)
        if alias:
            return CanonicalMatch(
                skill_id=alias.id,
                canonical_name=alias.canonical_name,
                confidence=0.96,
                method="alias",
                raw_text=raw,
            )
        query = f"{context or ''} {raw}".strip()
        nearest = self.nearest_neighbor(query, list(self.skills.values()))
        if nearest and nearest[1] >= self.threshold:
            skill = self.skills[nearest[0]]
            return CanonicalMatch(
                skill_id=skill.id,
                canonical_name=skill.canonical_name,
                confidence=nearest[1],
                method="embedding",
                raw_text=raw,
            )
        return CanonicalMatch(
            skill_id=None,
            canonical_name=None,
            confidence=0,
            method="UNRESOLVED",
            raw_text=raw,
        )

    @staticmethod
    def _ngram_neighbor(query: str, skills: list[SkillNode]) -> tuple[str, float] | None:
        """Small offline character-ngram embedding used when no vector service is set."""
        def vector(value: str) -> set[str]:
            compact = f"  {normalize_alias(value)}  "
            return {compact[index : index + 3] for index in range(max(0, len(compact) - 2))}

        query_vector = vector(query)
        if not query_vector:
            return None
        best_id, best_score = "", 0.0
        for skill in skills:
            target = vector(skill.canonical_name)
            union = query_vector | target
            score = len(query_vector & target) / len(union) if union else 0.0
            if score > best_score:
                best_id, best_score = skill.id, score
        return (best_id, best_score) if best_id else None
