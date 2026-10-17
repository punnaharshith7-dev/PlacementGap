from __future__ import annotations

import asyncio

from agent.contracts import CourseRecord, ProjectRecord, RunState, SourceSpan, StudentProfile
from agent.nodes.profile_normalize import profile_normalize_node


def test_explicitly_unsupported_skill_claim_does_not_become_evidence() -> None:
    profile_text = "Expert Kubernetes; no project, course, or work evidence provided."
    span = SourceSpan(
        source_doc_id="profile:contradiction",
        char_start=0,
        char_end=len(profile_text),
        extractor_confidence=0.9,
        quote=profile_text,
    )
    state = RunState(
        run_id="contradiction-test",
        student_id="contradiction-test",
        profile_text=profile_text,
        source_doc_id="profile:contradiction",
        profile=StudentProfile(
            student_id="contradiction-test",
            source_doc_id="profile:contradiction",
            raw_text=profile_text,
            projects=[ProjectRecord(name="Claim", description=profile_text, span=span)],
        ),
    )
    normalized = asyncio.run(profile_normalize_node(state.model_dump(mode="python")))
    result = RunState.model_validate(normalized)

    assert result.profile is not None
    assert "kubernetes" not in result.profile.demonstrated_skills


def test_normalized_evidence_span_quotes_the_exact_source_alias() -> None:
    profile_text = "Coursework: DSA\nBuilt a Kubernetes operator using Docker and A/B Testing."
    source_doc_id = "profile:span"
    course_line = "Coursework: DSA"
    project_line = "Built a Kubernetes operator using Docker and A/B Testing."
    project_start = profile_text.index(project_line)
    state = RunState(
        run_id="span-test",
        student_id="span-test",
        profile_text=profile_text,
        source_doc_id=source_doc_id,
        profile=StudentProfile(
            student_id="span-test",
            source_doc_id=source_doc_id,
            raw_text=profile_text,
            courses=[CourseRecord(
                name="DSA",
                description=course_line,
                span=SourceSpan(
                    source_doc_id=source_doc_id,
                    char_start=profile_text.index("DSA"),
                    char_end=profile_text.index("DSA") + 3,
                    extractor_confidence=0.9,
                    quote="DSA",
                ),
            )],
            projects=[ProjectRecord(
                name="Kubernetes operator",
                description=project_line,
                artifacts=["operator"],
                span=SourceSpan(
                    source_doc_id=source_doc_id,
                    char_start=project_start,
                    char_end=project_start + len(project_line),
                    extractor_confidence=0.9,
                    quote=project_line,
                ),
            )],
        ),
    )
    normalized = asyncio.run(profile_normalize_node(state.model_dump(mode="python")))
    result = RunState.model_validate(normalized)

    assert result.profile is not None
    evidence = {item.skill_id: item for item in result.profile.evidence}
    for skill_id, exact_quote in (
        ("data-structures-and-algorithms", "DSA"),
        ("kubernetes", "Kubernetes"),
        ("a-b-testing", "A/B Testing"),
    ):
        item = evidence[skill_id]
        assert item.span.quote == exact_quote
        assert result.profile.raw_text[item.span.char_start : item.span.char_end] == exact_quote
