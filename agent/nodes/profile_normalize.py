from __future__ import annotations

import os
import re
from typing import Any

from agent.contracts import (
    Evidence,
    ExperienceRecord,
    ProjectRecord,
    RunState,
    SkillLevel,
    SourceSpan,
)
from agent.nodes.common import node_event, trace_row
from memory.profile_store import save_profile
from ontology.canonicalizer import Canonicalizer


def _find_mentions(text: str, canonicalizer: Canonicalizer) -> list[tuple[str, int, int]]:
    folded = text.casefold()
    unsupported_lines: list[tuple[int, int]] = []
    line_start = 0
    for line in text.splitlines(keepends=True):
        if re.search(
            r"\b(no|without|never|not)\b.{0,120}\b(evidence|project|course|work|experience|used|artifact)s?\b",
            line,
            re.IGNORECASE,
        ):
            unsupported_lines.append((line_start, line_start + len(line)))
        line_start += len(line)
    mentions: list[tuple[int, int, str]] = []
    for skill in canonicalizer.skills.values():
        patterns = [skill.canonical_name]
        if os.getenv("PLACEMENTGAP_ABLATION") != "no_ontology":
            patterns.extend(skill.aliases)
        for pattern_text in patterns:
            if len(pattern_text.strip()) < 3:
                continue
            tokens = re.findall(r"[a-z0-9]+", pattern_text.casefold())
            phrase = (
                r"[\W_]+".join(re.escape(token) for token in tokens)
                if len(tokens) > 1
                else re.escape(pattern_text.casefold())
            )
            pattern = r"(?<![a-z0-9])" + phrase + r"(?![a-z0-9])"
            match = re.search(pattern, folded)
            if match:
                if any(start <= match.start() < end for start, end in unsupported_lines):
                    continue
                mentions.append((match.start(), match.end(), skill.id))
    mentions.sort(key=lambda row: (row[0], -(row[1] - row[0]), row[2]))
    unique: list[tuple[str, int, int]] = []
    seen: set[str] = set()
    for start, end, skill_id in mentions:
        if skill_id in seen:
            continue
        seen.add(skill_id)
        unique.append((skill_id, start, end))
    return unique


def _source_span(
    source_text: str,
    record_text: str,
    record_span: SourceSpan,
    start: int,
    end: int,
    confidence: float,
) -> SourceSpan:
    occurrences = [match.start() for match in re.finditer(re.escape(record_text), source_text)]
    record_start = (
        min(occurrences, key=lambda position: abs(position - record_span.char_start))
        if occurrences
        else record_span.char_start
    )
    char_start = record_start + start
    char_end = record_start + end
    return record_span.model_copy(update={
        "char_start": char_start,
        "char_end": char_end,
        "extractor_confidence": confidence,
        "quote": record_text[start:end],
    })


async def profile_normalize_node(raw: dict[str, Any]) -> dict[str, Any]:
    state = RunState.model_validate(raw)
    profile = state.profile
    if not profile:
        raise ValueError("Profile parsing did not produce a profile")
    if profile.demonstrated_skills:
        await save_profile(profile)
        return state.model_dump(mode="python")
    canonicalizer = Canonicalizer.from_default()
    best: dict[str, Evidence] = {}
    for course_record in profile.courses:
        record_text = course_record.description or course_record.name
        for skill_id, start, end in _find_mentions(record_text, canonicalizer):
            evidence = Evidence(
                skill_id=skill_id,
                level=SkillLevel.can_use,
                span=_source_span(profile.raw_text, record_text, course_record.span, start, end, 0.76),
                evidence_type="coursework",
                explanation=f"Coursework demonstrates foundational familiarity with {canonicalizer.skills[skill_id].canonical_name}.",
            )
            best.setdefault(skill_id, evidence)
    project_and_experience_records: list[ProjectRecord | ExperienceRecord] = [
        *profile.projects,
        *profile.experiences,
    ]
    for project_or_experience in project_and_experience_records:
        record_text = project_or_experience.description
        for skill_id, start, end in _find_mentions(record_text, canonicalizer):
            has_artifact = isinstance(project_or_experience, ProjectRecord) and bool(project_or_experience.artifacts) or bool(
                re.search(r"\b(built|developed|implemented|deployed|created|shipped)\b", project_or_experience.description, re.IGNORECASE)
            )
            owns_design = isinstance(project_or_experience, ProjectRecord) and project_or_experience.design_ownership
            level = SkillLevel.can_design if owns_design else SkillLevel.can_build if has_artifact else SkillLevel.can_use
            span = _source_span(
                profile.raw_text,
                record_text,
                project_or_experience.span,
                start,
                end,
                0.88 if has_artifact else 0.72,
            )
            evidence = Evidence(
                skill_id=skill_id,
                level=level,
                span=span,
                evidence_type="project" if isinstance(project_or_experience, ProjectRecord) else "experience",
                explanation="Evidence includes a described artifact and implementation activity." if has_artifact else "Mention appears in a project or experience description without a described artifact.",
            )
            current = best.get(skill_id)
            if current is None or evidence.level.rank > current.level.rank:
                best[skill_id] = evidence
    profile.evidence = list(best.values())
    profile.demonstrated_skills = {skill_id: evidence.level for skill_id, evidence in best.items()}
    await save_profile(profile)
    state.events.append(node_event(
        state, "profile_normalize", "node_end", demonstrated_skills=len(profile.demonstrated_skills)
    ))
    state.traces.append(trace_row(state, "profile_normalize", metadata={
        "demonstrated_skills": len(profile.demonstrated_skills),
        "course_cap": "can_use",
        "design_ownership_required": True,
        "tools_allowed": ["canonicalize_skill"],
    }))
    return state.model_dump(mode="python")
