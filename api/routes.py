from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent.contracts import RunState
from agent.tools.render_report import render_report
from api.auth_routes import authenticated_user
from api.run_store import RunStore

logger = logging.getLogger(__name__)
router = APIRouter()


class StartRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: str | None = Field(default=None, min_length=1, max_length=120)
    profile_text: str = Field(default="", max_length=500_000)
    profile_filename: str | None = Field(default=None, max_length=255)
    profile_file_base64: str | None = Field(default=None, max_length=20_000_000)
    jd_text: str = Field(default="", max_length=500_000)
    jd_url: str | None = Field(default=None, max_length=2048)
    role: str = Field(default="", max_length=200)
    company: str | None = Field(default=None, max_length=200)
    weeks: int = Field(default=8, ge=1, le=104)
    hours_per_week: float = Field(default=8, gt=0, le=100)
    max_cost_usd: float = Field(default=1, gt=0, le=100)
    max_tokens: int = Field(default=40_000, gt=0, le=2_000_000)

    @model_validator(mode="after")
    def one_jd_source(self) -> StartRunRequest:
        if not self.jd_text.strip() and not self.jd_url and not self.role.strip():
            raise ValueError("Provide pasted JD text, a JD URL, or a role name")
        if not self.profile_text.strip() and not self.profile_file_base64:
            raise ValueError("Provide profile text or a PDF/DOCX upload")
        if self.profile_file_base64:
            try:
                base64.b64decode(self.profile_file_base64, validate=True)
            except Exception as exc:
                raise ValueError("profile_file_base64 must contain valid base64 data") from exc
        return self


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject", "edit"]
    note: str = Field(default="", max_length=4000)
    edits: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_edits(self) -> ApprovalRequest:
        allowed = {"weeks", "hours_per_week", "hours_by_skill", "defer_skill_ids"}
        if set(self.edits) - allowed:
            raise ValueError("Unsupported edit fields; use weeks, hours_per_week, hours_by_skill, or defer_skill_ids")
        if "weeks" in self.edits and not 1 <= int(self.edits["weeks"]) <= 104:
            raise ValueError("weeks must be between 1 and 104")
        if "hours_per_week" in self.edits and not 0.5 <= float(self.edits["hours_per_week"]) <= 100:
            raise ValueError("hours_per_week must be between 0.5 and 100")
        for hours in self.edits.get("hours_by_skill", {}).values():
            if not 0.25 <= float(hours) <= 100:
                raise ValueError("hours_by_skill values must be between 0.25 and 100")
        return self


def _store(request: Request) -> RunStore:
    return cast(RunStore, request.app.state.run_store)


def _graph(request: Request) -> Any:
    return request.app.state.graph


async def _owned_run(run_id: str, request: Request) -> RunState:
    user = await authenticated_user(request)
    state = await _store(request).get(run_id)
    if not state or state.student_id != user["id"]:
        raise HTTPException(status_code=404, detail="Run not found")
    return state


async def _refresh_report(state: RunState, request: Request) -> None:
    if state.status != "completed" or not state.approved:
        raise HTTPException(status_code=409, detail="The approved report is not ready yet")
    rendered = render_report(state)
    state.report_markdown = str(rendered["markdown"])
    state.report_json = cast(dict[str, Any], rendered["json"])
    state.report_pdf = cast(bytes, rendered["pdf"])
    await _store(request).update(state)


def _config(run_id: str, request_id: str | None = None) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id, "run_id": run_id, "request_id": request_id or run_id}}


def _identity_key(body: StartRunRequest, supplied: str | None) -> str:
    if supplied:
        return supplied[:200]
    raw = json.dumps(body.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _merge_update(current: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if key in {"events", "traces"}:
            current.setdefault(key, [])
            current[key].extend(value)
        else:
            current[key] = value


async def _run_graph(
    request: Request,
    run_id: str,
    *,
    initial: RunState | None = None,
    resume: dict[str, Any] | None = None,
) -> None:
    store = _store(request)
    graph = _graph(request)
    started_nodes: set[str] = set()
    try:
        if initial is not None:
            current = initial.model_dump(mode="python")
            graph_input: Any = current
            await store.append_event(run_id, "run_start", {"run_id": run_id, "request_id": initial.request_id})
        else:
            saved = await store.get(run_id)
            if not saved:
                raise KeyError(f"Run {run_id} does not exist")
            current = saved.model_dump(mode="python")
            graph_input = Command(resume=resume or {"decision": "reject"})
            await store.append_event(run_id, "approval_resume", {"decision": (resume or {}).get("decision", "unknown")})

        async for chunk in graph.astream(graph_input, config=_config(run_id, current.get("request_id")), stream_mode="updates"):
            if not isinstance(chunk, dict):
                continue
            for node_name, node_update in chunk.items():
                if node_name == "__interrupt__":
                    interruptions = node_update if isinstance(node_update, (list, tuple)) else [node_update]
                    for item in interruptions:
                        value = getattr(item, "value", item)
                        await store.append_event(run_id, "interrupt", value if isinstance(value, dict) else {"payload": str(value)})
                    current["status"] = "awaiting_approval"
                    await store.update(RunState.model_validate(current))
                    continue
                if not isinstance(node_update, dict):
                    continue
                if node_name not in started_nodes:
                    started_nodes.add(node_name)
                    await store.append_event(run_id, "node_start", {
                        "node": node_name,
                        "started_at": datetime.now(UTC).isoformat(),
                        "request_id": current.get("request_id"),
                    })
                _merge_update(current, node_update)
                state = RunState.model_validate(current)
                await store.update(state)
                for trace in node_update.get("traces", []):
                    if trace.get("call_type") == "tool":
                        await store.append_event(run_id, "tool_call", trace)
                    elif trace.get("call_type") == "llm":
                        await store.append_event(run_id, "token_delta", {
                            "node": trace.get("node_name"),
                            "model": trace.get("model"),
                            "input_tokens": trace.get("input_tokens"),
                            "output_tokens": trace.get("output_tokens"),
                            "cost_usd": trace.get("cost_usd"),
                        })
                node_trace = next((row for row in reversed(state.traces) if row.node_name == node_name), None)
                await store.append_event(run_id, "node_end", {
                    "node": node_name,
                    "ended_at": datetime.now(UTC).isoformat(),
                    "latency_ms": node_trace.latency_ms if node_trace else 0,
                    "cost_usd": node_trace.cost_usd if node_trace else 0,
                    "trace_count": len(state.traces),
                    "status": state.status,
                })

        snapshot = await graph.aget_state(_config(run_id, current.get("request_id")))
        if snapshot and snapshot.values:
            final_state = RunState.model_validate(snapshot.values)
            if final_state.status not in {"awaiting_approval", "rejected"} and not final_state.approved and final_state.plan:
                final_state.status = "awaiting_approval"
            await store.update(final_state)
            if final_state.status not in {"awaiting_approval", "editing"}:
                await store.append_event(run_id, "run_end", {
                    "run_id": run_id,
                    "status": final_state.status,
                    "degraded": final_state.degraded,
                })
        else:
            await store.update(RunState.model_validate(current))
    except Exception as exc:
        logger.exception("Run %s failed", run_id)
        failed_state = await store.get(run_id)
        if failed_state:
            failed_state.status = "failed"
            failed_state.degraded = True
            failed_state.degraded_reasons.append(f"Run failed at an execution boundary: {type(exc).__name__}.")
            await store.update(failed_state)
        await store.append_event(run_id, "run_error", {"error": f"{type(exc).__name__}: {exc}"})
        await store.append_event(run_id, "run_end", {"run_id": run_id, "status": "failed"})


@router.post("/runs", status_code=202)
async def create_run(body: StartRunRequest, request: Request, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, Any]:
    user = await authenticated_user(request)
    if body.student_id and body.student_id != user["id"]:
        raise HTTPException(status_code=403, detail="Use the profile linked to your signed-in account.")
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id") or str(uuid.uuid4())
    student_id = str(user["id"])
    run_id = str(uuid.uuid4())
    state = RunState(
        run_id=run_id,
        student_id=student_id,
        profile_text=body.profile_text,
        profile_filename=body.profile_filename,
        profile_file_base64=body.profile_file_base64,
        jd_text=body.jd_text,
        jd_url=body.jd_url,
        role=body.role,
        company=body.company,
        weeks=body.weeks,
        hours_per_week=body.hours_per_week,
        max_cost_usd=body.max_cost_usd,
        max_tokens=body.max_tokens,
        request_id=request_id,
        source_doc_id=f"profile:{student_id}",
    )
    key = _identity_key(body, idempotency_key)
    stored, existing = await _store(request).create(state, key)
    if stored.student_id != user["id"]:
        raise HTTPException(status_code=404, detail="Run not found")
    if not existing:
        task = asyncio.create_task(_run_graph(request, run_id, initial=stored))
        request.app.state.tasks[run_id] = task
    return {"run_id": stored.run_id, "status": stored.status, "request_id": request_id, "idempotent_replay": existing}


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict[str, Any]:
    state = await _owned_run(run_id, request)
    return state.model_dump(mode="json", exclude={"profile_text", "profile_file_base64", "report_pdf"})


@router.get("/runs/{run_id}/trace")
async def get_trace(run_id: str, request: Request) -> dict[str, Any]:
    state = await _owned_run(run_id, request)
    events = await _store(request).events_after(run_id, 0)
    return {
        "run_id": run_id,
        "request_id": state.request_id,
        "traces": [item.model_dump(mode="json") for item in state.traces],
        "events": events,
        "budget": state.budget_snapshot,
    }


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, request: Request, after: int = 0) -> StreamingResponse:
    await _owned_run(run_id, request)

    async def generate() -> AsyncIterator[str]:
        cursor = after
        last_heartbeat = time.monotonic()
        terminal = {"completed", "rejected", "failed"}
        while True:
            if await request.is_disconnected():
                break
            events = await _store(request).events_after(run_id, cursor)
            for event in events:
                cursor = int(event["id"])
                payload = json.dumps(event["data"], ensure_ascii=False, default=str)
                yield f"id: {cursor}\nevent: {event['type']}\ndata: {payload}\n\n"
            current = await _store(request).get(run_id)
            if current and current.status in terminal and not events:
                break
            if time.monotonic() - last_heartbeat > 15:
                yield ": keep-alive\n\n"
                last_heartbeat = time.monotonic()
            await asyncio.sleep(0.4)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/runs/{run_id}/approve", status_code=202)
async def approve_run(run_id: str, body: ApprovalRequest, request: Request) -> dict[str, Any]:
    state = await _owned_run(run_id, request)
    if state.status != "awaiting_approval":
        raise HTTPException(status_code=409, detail=f"Run is {state.status}; approval is available only at the review gate")
    if body.decision == "edit" and not (body.note.strip() or body.edits):
        raise HTTPException(status_code=422, detail="An edit requires a note or structured plan changes")
    task = asyncio.create_task(_run_graph(
        request,
        run_id,
        resume={"decision": body.decision, "note": body.note, "edits": body.edits},
    ))
    request.app.state.tasks[run_id] = task
    return {"run_id": run_id, "status": "resuming", "decision": body.decision}


@router.get("/runs/{run_id}/report.md")
async def get_markdown(run_id: str, request: Request) -> FileResponse:
    state = await _owned_run(run_id, request)
    await _refresh_report(state, request)
    path = _store(request)._run_dir(run_id) / "report.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Markdown report is not ready")
    return FileResponse(path, media_type="text/markdown", filename="report.md")


@router.get("/runs/{run_id}/report.pdf")
async def get_pdf(run_id: str, request: Request) -> FileResponse:
    state = await _owned_run(run_id, request)
    await _refresh_report(state, request)
    path = _store(request)._run_dir(run_id) / "report.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF report is not ready")
    return FileResponse(path, media_type="application/pdf", filename="report.pdf")


@router.get("/runs/{run_id}/report.json")
async def get_json_report(run_id: str, request: Request) -> JSONResponse:
    state = await _owned_run(run_id, request)
    await _refresh_report(state, request)
    path = _store(request)._run_dir(run_id) / "report.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="JSON report is not ready")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


@router.get("/runs/{a}/diff/{b}")
async def diff_runs(a: str, b: str, request: Request) -> dict[str, Any]:
    left, right = await asyncio.gather(_owned_run(a, request), _owned_run(b, request))
    left_gaps = {gap.skill_id: gap.verdict.value for gap in left.gaps}
    right_gaps = {gap.skill_id: gap.verdict.value for gap in right.gaps}
    left_plan = {
        item.skill_id: {"week": item.week, "hours": item.hours, "weekly_hours": item.weekly_hours}
        for week in (left.plan.weeks if left.plan else []) for item in week.items
    }
    right_plan = {
        item.skill_id: {"week": item.week, "hours": item.hours, "weekly_hours": item.weekly_hours}
        for week in (right.plan.weeks if right.plan else []) for item in week.items
    }
    return {
        "run_a": a,
        "run_b": b,
        "gap_verdicts": {
            skill: {"a": left_gaps.get(skill), "b": right_gaps.get(skill)}
            for skill in sorted(set(left_gaps) | set(right_gaps))
            if left_gaps.get(skill) != right_gaps.get(skill)
        },
        "plan_items": {
            skill: {"a": left_plan.get(skill), "b": right_plan.get(skill)}
            for skill in sorted(set(left_plan) | set(right_plan))
            if left_plan.get(skill) != right_plan.get(skill)
        },
        "satisfied_a": left.plan.satisfied_skills if left.plan else [],
        "satisfied_b": right.plan.satisfied_skills if right.plan else [],
        "deferred_a": [item.model_dump(mode="json") for item in left.plan.deferred] if left.plan else [],
        "deferred_b": [item.model_dump(mode="json") for item in right.plan.deferred] if right.plan else [],
    }


@router.get("/evals/latest")
async def latest_eval(request: Request) -> dict[str, Any]:
    reports = Path("evals/reports")
    candidates = sorted(
        [*reports.glob("dev-*.json"), *reports.glob("heldout-*.json")],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if reports.exists() else []
    if not candidates:
        raise HTTPException(status_code=404, detail="No evaluation report is available")
    result: dict[str, Any] = cast(dict[str, Any], json.loads(candidates[0].read_text(encoding="utf-8")))
    if reports.exists():
        ablation_files = sorted(reports.glob("ablation-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        if ablation_files:
            ablation_data = json.loads(ablation_files[0].read_text(encoding="utf-8"))
            result["ablations"] = []
            for variant, payload in ablation_data.get("variants", {}).items():
                metrics = payload.get("metrics", {})
                result["ablations"].append({
                    "variant": variant,
                    "success_rate": metrics.get("end_to_end", {}).get("task_success_rate"),
                    "plan_validity": metrics.get("end_to_end", {}).get("plan_validity", {}).get("pass_rate"),
                    "cost_per_run": metrics.get("ops", {}).get("cost_usd", {}).get("p50"),
                    "p95_latency_ms": metrics.get("ops", {}).get("latency_ms", {}).get("p95"),
                    "status": payload.get("status"),
                })
        chaos_files = sorted(reports.glob("chaos-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        if chaos_files:
            chaos_data = json.loads(chaos_files[0].read_text(encoding="utf-8"))
            result.setdefault("metrics", {}).setdefault("trajectory", {})["recovery_by_failure_type"] = {
                failure: values.get("recovery_rate", 0)
                for failure, values in chaos_data.get("recovery_by_failure_type", {}).items()
            }
    return result
