from __future__ import annotations

import fitz

from agent.contracts import JobDescription, Plan, RunState, StudentProfile
from agent.tools.render_report import render_report


def _empty_analysis_state() -> RunState:
    return RunState(
        run_id="empty-analysis",
        student_id="student-1",
        profile_text="dbms, python",
        jd_text="Software",
        role="Software Engineer",
        status="approved",
        approved=True,
        degraded=True,
        degraded_reasons=["No structured course, project, or experience lines were recognized."],
        profile=StudentProfile(
            student_id="student-1",
            source_doc_id="profile-text",
            raw_text="dbms, python",
            degraded=True,
            degraded_reason="No structured course, project, or experience lines were recognized.",
        ),
        job=JobDescription(
            source_doc_id="provided_text",
            role="Software Engineer",
            text="Software",
            discovery_tier="provided_text",
            content_hash="empty-job",
            degraded=True,
            degraded_reason="No requirements were extracted from the supplied job text.",
        ),
        plan=Plan(total_budget_hours=64),
    )


def test_empty_analysis_report_explains_missing_evidence_without_empty_sections() -> None:
    rendered = render_report(_empty_analysis_state())
    markdown = str(rendered["markdown"])

    assert "This run could not produce a reliable skill-gap analysis." in markdown
    assert "0 course records, 0 project records, and 0 experience records" in markdown
    assert "No job requirements were extracted" in markdown
    assert "## What to provide next" in markdown
    assert "## Week-by-week plan" not in markdown
    assert rendered["json"]["input_quality"]["job_requirement_count"] == 0


def test_empty_analysis_pdf_contains_actionable_body_and_uses_one_page() -> None:
    rendered = render_report(_empty_analysis_state())
    document = fitz.open(stream=rendered["pdf"], filetype="pdf")
    text = "\n".join(page.get_text() for page in document)

    assert document.page_count == 1
    assert "What to provide next" in text
    assert "complete job description" in text.lower()
    assert "course records" in text.lower()
    assert len(text) > 500
