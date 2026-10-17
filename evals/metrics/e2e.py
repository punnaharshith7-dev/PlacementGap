from __future__ import annotations

from typing import Any

from agent.contracts import PlanRequest, RunState
from evals.checkers.plan_validity import check_plan


def end_to_end_metrics(cases: list[dict[str, Any]], states: list[RunState]) -> dict[str, Any]:
    valid = 0
    violations: dict[str, int] = {}
    successful = 0
    grounded_claims = 0
    total_claims = 0
    for case, state in zip(cases, states, strict=True):
        if state.plan:
            request = PlanRequest(gaps=state.gaps, weeks=state.weeks, hours_per_week=state.hours_per_week)
            check = check_plan(request, state.plan)
            valid += int(check.valid)
            for name, count in check.breakdown.items():
                violations[name] = violations.get(name, 0) + count
        labels = case.get("labels", {})
        expected_ids = {row["skill_id"] for row in labels.get("requirements", [])}
        predicted_ids = {gap.skill_id for gap in state.gaps}
        plan_accounts = set()
        if state.plan:
            plan_accounts.update(item.skill_id for week in state.plan.weeks for item in week.items)
            plan_accounts.update(item.skill_id for item in state.plan.deferred)
            plan_accounts.update(state.plan.satisfied_skills)
        successful += int(expected_ids.issubset(predicted_ids) and expected_ids.issubset(plan_accounts) and bool(state.plan))
        claims = state.report_json.get("provenance", []) if state.report_json else []
        source_texts = {}
        if state.profile:
            source_texts[state.profile.source_doc_id] = state.profile.raw_text
        if state.job:
            source_texts[state.job.source_doc_id] = state.job.text
        total_claims += len(claims)
        for claim in claims:
            source = source_texts.get(str(claim.get("source_doc_id", "")), "")
            start = int(claim.get("char_start", -1))
            end = int(claim.get("char_end", -1))
            quote = str(claim.get("quote", ""))
            span_text = source[start:end] if 0 <= start < end <= len(source) else ""
            grounded_claims += int(
                bool(source and span_text and quote)
                and quote.casefold() in source.casefold()
                and span_text.casefold() in quote.casefold()
            )
    size = len(cases)
    return {
        "task_success_rate": successful / size if size else 0.0,
        "plan_validity": {"pass_rate": valid / size if size else 0.0, "violation_breakdown": violations},
        "groundedness": grounded_claims / total_claims if total_claims else 0.0,
        "grounded_claims": grounded_claims,
        "total_claims": total_claims,
    }
