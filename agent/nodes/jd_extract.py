from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent.budget import RunBudget
from agent.contracts import RequirementSpec, RunState, SkillLevel, SourceSpan
from agent.llm import LLMClient
from agent.nodes.common import node_event, trace_row
from memory.semantic_cache import cache_jd, get_cached_jd
from ontology.canonicalizer import Canonicalizer, normalize_alias


class RequirementCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill_text: str = Field(min_length=2, max_length=100)
    hard_requirement: bool = True
    required_level: SkillLevel = SkillLevel.can_use
    years_hint: float | None = Field(default=None, ge=0, le=80)
    source_quote: str = Field(min_length=2, max_length=500)


class RequirementCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirements: list[RequirementCandidate] = Field(max_length=200)


def _rule_extract(
    job_text: str,
    source_doc_id: str,
    canonicalizer: Canonicalizer,
    role: str | None = None,
) -> list[RequirementSpec]:
    folded = job_text.casefold()
    role_header_end = _role_header_end(job_text, role)
    candidates: list[tuple[int, int, str, str]] = []
    # Prefer multiword labels; aliases are checked too, but very short aliases are ignored.
    for skill in canonicalizer.skills.values():
        labels = [skill.canonical_name]
        if os.getenv("PLACEMENTGAP_ABLATION") != "no_ontology":
            labels.extend(skill.aliases)
        for label in labels:
            normalized = normalize_alias(label)
            if len(normalized) < 3:
                continue
            pattern = _skill_pattern(label)
            for match in re.finditer(pattern, folded):
                if match.start() < role_header_end:
                    continue
                candidates.append((match.start(), match.end(), skill.id, skill.canonical_name))
    candidates.sort(key=lambda row: (row[0], -(row[1] - row[0]), row[2]))
    selected: list[tuple[int, int, str, str]] = []
    occupied_until = -1
    seen_skills: set[str] = set()
    for candidate in candidates:
        start, end, skill_id, _ = candidate
        if start < occupied_until:
            continue
        if skill_id in seen_skills:
            occupied_until = end
            continue
        selected.append(candidate)
        occupied_until = end
        seen_skills.add(skill_id)

    requirements: list[RequirementSpec] = []
    for start, end, skill_id, canonical_name in selected:
        context = folded[max(0, start - 70) : min(len(folded), end + 70)]
        hard = not _is_preferred_requirement(job_text, start, end)
        level = SkillLevel.can_design if any(token in context for token in ("architect", "design ownership")) else (
            SkillLevel.can_build if any(token in context for token in ("build", "implement", "develop", "production")) else SkillLevel.can_use
        )
        year_match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*years?", context)
        quote = job_text[max(0, start - 40) : min(len(job_text), end + 60)].strip()
        requirements.append(RequirementSpec(
            skill_text=job_text[start:end],
            hard_requirement=hard,
            required_level=level,
            years_hint=float(year_match.group(1)) if year_match else None,
            span=SourceSpan(
                source_doc_id=source_doc_id,
                char_start=start,
                char_end=end,
                extractor_confidence=0.86,
                quote=quote,
            ),
            skill_id=skill_id,
            canonical_name=canonical_name,
            canonical_confidence=1,
            canonical_method="exact",
        ))
    return requirements


def _skill_pattern(label: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", label.casefold())
    phrase = r"[\W_]+".join(re.escape(token) for token in tokens) if len(tokens) > 1 else re.escape(label.casefold())
    return r"(?<![a-z0-9])" + phrase + r"(?![a-z0-9])"


def _role_header_end(job_text: str, role: str | None) -> int:
    first_line_end = job_text.find("\n")
    if first_line_end < 0:
        first_line_end = len(job_text)
    first_line = job_text[:first_line_end]
    separator = re.search(r"[:—–|]", first_line)
    if separator is None:
        return 0
    header = first_line[: separator.start()].strip()
    if role and normalize_alias(header) == normalize_alias(role):
        return separator.end()
    return 0


def _is_preferred_requirement(job_text: str, start: int, end: int) -> bool:
    markers = r"preferred|nice to have|bonus|plus|ideally"
    right = job_text[end : min(len(job_text), end + 60)]
    right_marker = re.search(rf"\b(?:{markers})\b", right, re.IGNORECASE)
    if right_marker:
        bridge = right[: right_marker.start()]
        if not re.search(r"[.;\n]", bridge) and len(re.findall(r"[a-z0-9]+", bridge, re.IGNORECASE)) <= 4:
            return True
    left = job_text[max(0, start - 60) : start]
    left_markers = list(re.finditer(rf"\b(?:{markers})\b", left, re.IGNORECASE))
    if left_markers:
        bridge = left[left_markers[-1].end() :]
        if not re.search(r"[.;\n]", bridge) and len(re.findall(r"[a-z0-9]+", bridge, re.IGNORECASE)) <= 4:
            return True
    return False


def _validate_candidates(
    state: RunState, candidates: RequirementCandidates, canonicalizer: Canonicalizer
) -> list[RequirementSpec]:
    job = state.job
    if not job:
        return []
    result: list[RequirementSpec] = []
    for candidate in candidates.requirements:
        match = re.search(re.escape(candidate.source_quote), job.text, flags=re.IGNORECASE)
        if not match:
            continue
        normalized_text = candidate.skill_text.strip()
        if len(normalized_text) < 2 or len(normalized_text) > 100:
            continue
        canonical = canonicalizer.canonicalize(normalized_text, candidate.source_quote)
        # Fuzzy fields must be grounded in a real source quote and a sane canonical skill.
        result.append(RequirementSpec(
            skill_text=normalized_text,
            hard_requirement=candidate.hard_requirement,
            required_level=candidate.required_level,
            years_hint=candidate.years_hint,
            span=SourceSpan(
                source_doc_id=job.source_doc_id,
                char_start=match.start(),
                char_end=match.end(),
                extractor_confidence=0.78,
                quote=candidate.source_quote,
            ),
            skill_id=canonical.skill_id,
            canonical_name=canonical.canonical_name,
            canonical_confidence=canonical.confidence,
            canonical_method=canonical.method,
        ))
    return result


async def jd_extract_node(raw: dict[str, Any]) -> dict[str, Any]:
    state = RunState.model_validate(raw)
    if not state.job:
        raise ValueError("JD discovery did not provide a validated JobDescription")
    canonicalizer = Canonicalizer.from_default()
    requirements = _rule_extract(state.job.text, state.job.source_doc_id, canonicalizer, state.job.role)
    cached, cache_hit = await get_cached_jd(
        state.job.content_hash,
        state.job.role,
        state.job.text,
    )
    if cache_hit and cached:
        cached_ids = {str(item) for item in cached.get("skill_ids", [])}
        if cached_ids:
            requirements = [item for item in requirements if item.skill_id in cached_ids]
    # The optional LLM only proposes fuzzy extractions. Deterministic source-span validation
    # and canonicalization run before any proposal enters the state.
    budget = RunBudget.restore(state.budget_snapshot, max_usd=state.max_cost_usd, max_tokens=state.max_tokens)
    client = LLMClient(state.run_id, budget)
    if client.enabled and not cache_hit:
        response, degraded, reason = await client.structured(
            node_name="jd_extract",
            payload=state.job.text,
            schema=RequirementCandidates,
            degraded_default=RequirementCandidates(requirements=[]),
        )
        state.traces.extend(client.traces)
        if not degraded:
            proposed = _validate_candidates(state, response, canonicalizer)
            by_id = {item.skill_id: item for item in requirements}
            for item in proposed:
                if item.skill_id:
                    by_id.setdefault(item.skill_id, item)
            requirements = list(by_id.values())
        else:
            state.degraded = True
            state.degraded_reasons.append(f"JD extraction used deterministic fallback: {reason}")
    state.budget_snapshot = budget.snapshot()
    if budget.degraded:
        state.degraded = True
        if budget.reduction_reason and budget.reduction_reason not in state.degraded_reasons:
            state.degraded_reasons.append(budget.reduction_reason)
    state.job.requirements = requirements
    await cache_jd(
        state.job.content_hash,
        state.job.role,
        {"skill_ids": [item.skill_id for item in requirements if item.skill_id]},
        state.job.text,
    )
    if cache_hit:
        state.traces.append(trace_row(
            state,
            "jd_extract",
            call_type="tool",
            model="semantic_cache",
            cache_hit=True,
            metadata={"role": state.job.role, "content_hash": state.job.content_hash, "ttl_days": 14},
        ))
    state.events.append(node_event(state, "jd_extract", "node_end", requirement_count=len(requirements)))
    state.traces.append(trace_row(
        state, "jd_extract", metadata={
            "requirements": len(requirements),
            "semantic_cache_hit": cache_hit,
            "unresolved": sum(item.skill_id is None for item in requirements),
            "tools_allowed": ["canonicalize_skill"],
            "untrusted_input_fenced": True,
        }
    ))
    return state.model_dump(mode="python")
