from __future__ import annotations

import asyncio
import base64
import re
from typing import Any

from agent.contracts import (
    CourseRecord,
    ExperienceRecord,
    ProjectRecord,
    StudentProfile,
)
from agent.nodes.common import node_event, state_from, tool_trace, trace_row
from agent.tools.base import execute_tool
from agent.tools.parse_document import parse_document, parse_text

_HEADING = re.compile(r"^(education|coursework|projects?|experience|work experience|skills)\s*:?$", re.IGNORECASE)


def _records(text: str, source_doc_id: str) -> tuple[list[CourseRecord], list[ProjectRecord], list[ExperienceRecord]]:
    parsed = parse_text(text, source_doc_id)
    courses: list[CourseRecord] = []
    projects: list[ProjectRecord] = []
    experiences: list[ExperienceRecord] = []
    section = ""
    for segment in parsed.segments:
        line = segment.text.strip().lstrip("-•* ")
        if not line:
            continue
        heading = _HEADING.match(line)
        if heading:
            section = heading.group(1).casefold()
            continue
        span = segment.span
        course_match = re.search(r"(?:coursework|courses?)\s*:?\s*(.+)", line, re.IGNORECASE)
        if course_match:
            names = [part.strip() for part in re.split(r"[,;|]", course_match.group(1)) if part.strip()]
            for name in names:
                pos = text.find(name, span.char_start, span.char_end)
                start = pos if pos >= 0 else span.char_start
                courses.append(CourseRecord(
                    name=name,
                    description=line,
                    grade=None,
                    skills=[name],
                    span=span.model_copy(update={"char_start": start, "char_end": start + len(name), "quote": name}),
                ))
            continue
        if section in {"education", "coursework"} or re.search(r"\b(course|cgpa|gpa|credits?)\b", line, re.IGNORECASE):
            if re.search(r"\b(cgpa|gpa)\b", line, re.IGNORECASE):
                continue
            courses.append(CourseRecord(name=line, description=line, skills=[line], span=span))
        elif section in {"project", "projects"} or re.search(r"\b(built|developed|implemented|designed|created|deployed)\b", line, re.IGNORECASE):
            artifact_matches = re.findall(r"\b(API|application|app|dashboard|website|service|model|pipeline|tool|system|platform|engine|mobile app)\b", line, re.IGNORECASE)
            design = bool(re.search(r"\b(architected|designed the architecture|owned system design)\b", line, re.IGNORECASE))
            projects.append(ProjectRecord(
                name=re.split(r"[:—-]", line, maxsplit=1)[0][:120],
                description=line,
                artifacts=list(dict.fromkeys(item.casefold() for item in artifact_matches)),
                skills=[line],
                design_ownership=design,
                span=span,
            ))
        elif section in {"experience", "work experience"} or re.search(r"\b(intern|engineer|developer|analyst|at [A-Z])\b", line, re.IGNORECASE):
            experiences.append(ExperienceRecord(
                title=line[:120],
                organization="",
                description=line,
                skills=[line],
                span=span,
            ))
    return courses, projects, experiences


async def profile_parse_node(raw: dict[str, Any]) -> dict[str, Any]:
    state = state_from(raw)
    if state.profile is not None:
        state.events.append(node_event(state, "profile_parse", "node_end", warm_profile=True))
        state.traces.append(trace_row(state, "profile_parse", metadata={"warm_profile": True, "parse_skipped": True, "tools_allowed": []}))
        return state.model_dump(mode="python")
    if state.profile_file_base64:
        file_bytes = base64.b64decode(state.profile_file_base64, validate=True)
        filename = state.profile_filename or "transcript.txt"
        file_kind = filename.rsplit(".", 1)[-1]
        parse_result = await execute_tool(
            name="parse_document",
            call=lambda: asyncio.to_thread(parse_document, file_bytes, file_kind, state.source_doc_id),
            timeout_s=30,
            trace=lambda row: tool_trace(state, "profile_parse", row),
        )
        if parse_result.status == "ok" and parse_result.data:
            parsed = parse_result.data
        else:
            parsed = parse_text("", state.source_doc_id)
            state.degraded = True
            state.degraded_reasons.append(
                f"Document parsing failed after retries: {parse_result.reason or parse_result.status}."
            )
        text = parsed.text
        courses, projects, experiences = await asyncio.to_thread(_records, text, state.source_doc_id)
        parser_tier = parsed.parser_tier
        parse_degraded = parsed.degraded or parse_result.status != "ok"
        parse_reason = parsed.degraded_reason or parse_result.reason
    else:
        text = state.profile_text
        courses, projects, experiences = await asyncio.to_thread(_records, text, state.source_doc_id)
        parser_tier = "text_heuristic"
        parse_degraded = False
        parse_reason = None
    profile = StudentProfile(
        student_id=state.student_id,
        source_doc_id=state.source_doc_id,
        raw_text=text,
        courses=courses,
        projects=projects,
        experiences=experiences,
        parser_tier=parser_tier,
        degraded=parse_degraded or not bool(courses or projects or experiences),
        degraded_reason=parse_reason or ("No structured course, project, or experience lines were recognized." if not (courses or projects or experiences) else None),
    )
    state.profile = profile
    if profile.degraded:
        state.degraded = True
        state.degraded_reasons.append(profile.degraded_reason or "Profile parser found no structured records.")
    state.events.append(node_event(
        state, "profile_parse", "node_end", courses=len(courses), projects=len(projects), experiences=len(experiences)
    ))
    state.traces.append(trace_row(state, "profile_parse", metadata={
        "parser_tier": profile.parser_tier,
        "courses": len(courses),
        "projects": len(projects),
        "experiences": len(experiences),
        "tools_allowed": ["parse_document"],
    }))
    return state.model_dump(mode="python")
