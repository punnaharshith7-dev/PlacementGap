from __future__ import annotations

import os
import re
from typing import Any

from agent.contracts import Gap, GapVerdict, RunState, SkillLevel
from agent.nodes.common import node_event, trace_row
from agent.tools.estimate_effort import estimate_effort
from ontology.canonicalizer import Canonicalizer
from ontology.graph import SkillGraph


async def gap_analysis_node(raw: dict[str, Any]) -> dict[str, Any]:
    state = RunState.model_validate(raw)
    if not state.job or not state.profile:
        raise ValueError("Both JD extraction and profile normalization must finish before gap analysis")
    canonicalizer = Canonicalizer.from_default()
    graph = SkillGraph()
    gaps: list[Gap] = []
    for requirement in state.job.requirements:
        skill_id = requirement.skill_id
        skill = canonicalizer.skills.get(skill_id or "")
        if not skill:
            normalized = re.sub(r"[^a-z0-9]+", "-", requirement.skill_text.casefold()).strip("-")
            skill_id = f"unresolved:{normalized[:60]}"
            canonical_name = requirement.skill_text
            demand = requirement.market_demand_weight
            prerequisites: list[str] = []
        else:
            skill_id = skill.id
            canonical_name = skill.canonical_name
            demand = skill.market_demand_weight
            prerequisites = [] if os.getenv("PLACEMENTGAP_ABLATION") == "no_ontology" else graph.direct_prerequisites(skill_id)

        demonstrated = state.profile.demonstrated_skills.get(skill_id, SkillLevel.aware)
        evidence = [item for item in state.profile.evidence if item.skill_id == skill_id]
        related_evidence = []
        if skill and not evidence and os.getenv("PLACEMENTGAP_ABLATION") != "no_ontology":
            for item in state.profile.evidence:
                if graph.is_adjacent(skill_id, item.skill_id) or item.skill_id in prerequisites:
                    related_evidence.append(item)
        if evidence and demonstrated.rank >= requirement.required_level.rank:
            verdict = GapVerdict.has
        elif evidence or related_evidence:
            verdict = GapVerdict.partial
        else:
            verdict = GapVerdict.missing
        if verdict == GapVerdict.has:
            delta = 0
        elif verdict == GapVerdict.partial:
            delta = max(1, requirement.required_level.rank - demonstrated.rank)
        else:
            delta = max(1, requirement.required_level.rank)
        supporting = evidence or related_evidence
        if verdict == GapVerdict.has:
            rationale = f"Profile evidence demonstrates {demonstrated.value}, meeting the stated {requirement.required_level.value} level."
        elif related_evidence:
            rationale = "No direct evidence was found; adjacent or prerequisite evidence supports partial transfer, but the required skill remains unverified."
        elif evidence:
            rationale = f"Direct evidence exists at {demonstrated.value}, below the requested {requirement.required_level.value} level."
        else:
            rationale = "No source-backed profile evidence matched this job requirement."
        effort = estimate_effort(skill_id, demonstrated, requirement.required_level)
        gaps.append(Gap(
            skill_id=skill_id,
            canonical_name=canonical_name,
            required_level=requirement.required_level,
            demonstrated_level=demonstrated,
            verdict=verdict,
            level_delta=min(3, delta),
            effort_hours=effort,
            hard_requirement=requirement.hard_requirement,
            market_demand_weight=demand,
            prerequisite_ids=prerequisites,
            evidence=supporting,
            rationale=rationale,
        ))
    state.gaps = gaps
    state.events.append(node_event(state, "gap_analysis", "node_end", gap_count=len(gaps)))
    state.traces.append(trace_row(state, "gap_analysis", metadata={
        "gap_count": len(gaps),
        "verdicts": {verdict.value: sum(item.verdict == verdict for item in gaps) for verdict in GapVerdict},
        "traversals": "direct_prerequisite_and_adjacency",
        "tools_allowed": ["search_skill_graph", "evidence_search", "estimate_effort"],
    }))
    return state.model_dump(mode="python")
