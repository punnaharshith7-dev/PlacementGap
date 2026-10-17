from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class JDResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    company: str
    location: str
    text: str
    url: str | None = None
    fixture: bool = True


def search_jds(role: str, company: str | None = None, location: str | None = None, n: int = 3) -> list[JDResult]:
    """Search a frozen job corpus offline; live connectors can be added via provider config."""
    del company, location
    fixture_path = Path(__file__).parents[2] / "evals" / "datasets" / "job_corpus.yaml"
    if os.getenv("PLACEMENTGAP_FIXTURES", "1") != "1" or not fixture_path.exists():
        return []
    rows = yaml.safe_load(fixture_path.read_text(encoding="utf-8")).get("jobs", [])
    query_tokens = set(role.casefold().split())
    ranked = sorted(
        rows,
        key=lambda row: (
            -len(query_tokens & set(str(row["role"]).casefold().split())),
            str(row["role"]),
        ),
    )
    return [JDResult.model_validate(row) for row in ranked[: max(1, n)]]
