from __future__ import annotations

import re

from agent.contracts import Evidence, StudentProfile


def evidence_search(skill_id: str, profile: StudentProfile, k: int = 5) -> list[Evidence]:
    """Search only this student's normalized evidence, ranked by lexical relevance."""
    tokens = set(re.findall(r"[a-z0-9]+", skill_id.replace("-", " ").casefold()))
    ranked: list[tuple[int, Evidence]] = []
    for evidence in profile.evidence:
        evidence_tokens = set(re.findall(r"[a-z0-9]+", evidence.skill_id.replace("-", " ").casefold()))
        score = len(tokens & evidence_tokens) + (5 if evidence.skill_id == skill_id else 0)
        if score:
            ranked.append((score, evidence))
    ranked.sort(key=lambda item: (-item[0], item[1].span.char_start))
    return [item[1] for item in ranked[:k]]
