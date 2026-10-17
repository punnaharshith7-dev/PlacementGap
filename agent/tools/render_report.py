from __future__ import annotations

import re
from html import escape
from typing import Any

from agent.contracts import RunState


def _footnote(span: Any) -> str:
    return f"{span.source_doc_id}:{span.char_start}-{span.char_end}"


def render_report(state: RunState) -> dict[str, Any]:
    job = state.job
    plan = state.plan
    profile_record_counts = {
        "courses": len(state.profile.courses) if state.profile else 0,
        "projects": len(state.profile.projects) if state.profile else 0,
        "experiences": len(state.profile.experiences) if state.profile else 0,
    }
    profile_record_count = sum(profile_record_counts.values())
    requirement_count = len(job.requirements) if job else 0
    plan_items = [item for week in plan.weeks for item in week.items] if plan else []
    provenance: list[dict[str, Any]] = []
    provenance_by_skill: dict[str, list[int]] = {}
    input_quality_notes: list[str] = []

    if profile_record_count == 0:
        input_quality_notes.append(
            "No structured course, project, or experience records were recognized in the profile."
        )
    if requirement_count == 0:
        input_quality_notes.append(
            "No job requirements were extracted from the supplied role or job description."
        )
    for reason in state.degraded_reasons:
        if reason and reason not in input_quality_notes:
            input_quality_notes.append(reason)
    input_quality_status = "limited" if input_quality_notes else "ready"

    def table_cell(value: str) -> str:
        return " ".join(value.replace("|", r"\|").split())

    lines = [
        f"# PlacementGap learning plan: {state.role or (job.role if job else 'target role')}",
        "",
        f"Run ID: `{state.run_id}`  ",
        f"Discovery tier: `{state.discovery_tier or (job.discovery_tier if job else 'unknown')}`  ",
        f"Status: `{state.status}`",
        "",
        "## Executive summary",
        "",
    ]
    if input_quality_status == "limited":
        lines.append("This run could not produce a reliable skill-gap analysis.")
        lines.append("")
        lines.append(
            f"It recognized {profile_record_counts['courses']} course records, "
            f"{profile_record_counts['projects']} project records, and "
            f"{profile_record_counts['experiences']} experience records, and extracted "
            f"{requirement_count} job requirements. No unsupported skill claims or learning objectives "
            "have been added to this report."
        )
        lines.append("")
        if state.degraded_reasons:
            lines.append("Processing note: " + "; ".join(state.degraded_reasons))
            lines.append("")
    if plan and plan_items:
        active_weeks = sum(bool(week.items) for week in plan.weeks)
        lines.append(
            f"The plan schedules {len(plan_items)} learning objectives over {active_weeks} active weeks, using "
            f"{plan.total_hours:g} of {plan.total_budget_hours:g} available hours."
        )
    elif plan and plan.satisfied_skills and requirement_count > 0:
        lines.append("The extracted requirements are already supported by your profile; no additional study hours were scheduled.")
    elif requirement_count == 0:
        lines.append("A learning schedule was withheld because there were no verified job requirements to plan against.")
    elif plan and plan.deferred:
        lines.append("The report lists the remaining objectives as deferred because they could not fit within the selected schedule.")
    else:
        lines.append("No learning schedule was produced for this run.")
    lines.extend(["", "## Gap analysis", ""])
    rationales: list[str] = []
    if state.gaps:
        lines.extend(["| Requirement | Your evidence | Verdict | Level delta |", "|---|---|---:|---:|"])
    else:
        gap_message = (
            "No job requirements were extracted, so no gap verdicts can be shown. Provide a full job description, a job URL, or a specific role and company."
            if requirement_count == 0
            else "No gap records were returned for the extracted requirements. Review the input quality notes before relying on this result."
        )
        lines.extend([gap_message, ""])
    for index, gap in enumerate(state.gaps, 1):
        snippets = []
        source_refs: list[int] = []
        for evidence in gap.evidence:
            note_id = len(provenance) + 1
            source_refs.append(note_id)
            provenance.append({
                "id": note_id,
                "source_doc_id": evidence.span.source_doc_id,
                "char_start": evidence.span.char_start,
                "char_end": evidence.span.char_end,
                "extractor_confidence": evidence.span.extractor_confidence,
                "quote": evidence.span.quote,
                "claim": f"Student evidence for {gap.canonical_name}",
            })
            snippets.append(f"{evidence.span.quote[:90]} [^{note_id}]")
        if not snippets:
            snippets = ["No matching profile evidence"]
        requirement = next((req for req in job.requirements if req.skill_id == gap.skill_id), None) if job else None
        if requirement:
            note_id = len(provenance) + 1
            source_refs.append(note_id)
            provenance.append({
                "id": note_id,
                "source_doc_id": requirement.span.source_doc_id,
                "char_start": requirement.span.char_start,
                "char_end": requirement.span.char_end,
                "extractor_confidence": requirement.span.extractor_confidence,
                "quote": requirement.span.quote,
                "claim": f"Job requirement for {gap.canonical_name}",
            })
            requirement_text = f"{requirement.skill_text} [^{note_id}]"
        else:
            requirement_text = gap.canonical_name
        provenance_by_skill[gap.skill_id] = source_refs
        lines.append(
            f"| {table_cell(requirement_text)} | {table_cell('; '.join(snippets))} | "
            f"**{table_cell(gap.verdict.value)}** | {gap.level_delta} |"
        )
        citations = " ".join(f"[^{note_id}]" for note_id in source_refs)
        rationales.append(f"{index}. **{gap.canonical_name}** — {gap.rationale} {citations}".rstrip())
    if rationales:
        lines.extend(["", "### Verdict rationale", "", *rationales])
    if plan and plan.satisfied_skills:
        lines.extend(["", "## Already demonstrated", ""])
        gap_names = {gap.skill_id: gap.canonical_name for gap in state.gaps}
        for skill_id in plan.satisfied_skills:
            citations = " ".join(
                f"[^{note_id}]" for note_id in provenance_by_skill.get(skill_id, [])
            )
            lines.append(
                f"- **{gap_names.get(skill_id, skill_id)}** already meets the requested level; no study hours scheduled. {citations}".rstrip()
            )
        lines.append("")
    if plan and plan_items:
        lines.extend(["## Week-by-week plan", ""])
        all_items = plan_items
        for week in plan.weeks:
            if not week.items:
                continue
            lines.append(f"### Week {week.week} — {week.scheduled_hours:g}/{week.capacity_hours:g} hours")
            sessions = [
                (item, item.weekly_hours.get(week.week, item.hours if item.week == week.week else 0.0))
                for item in all_items
            ]
            for item, session_hours in sessions:
                if session_hours <= 0:
                    continue
                citations = " ".join(
                    f"[^{note_id}]" for note_id in provenance_by_skill.get(item.skill_id, [])
                )
                if item.week == week.week:
                    lines.append(
                        f"- **{item.canonical_name}** ({item.hours:g}h total; {session_hours:g}h this week): "
                        f"{item.outcome} {citations}".rstrip()
                    )
                    for resource in item.resources:
                        lines.append(f"  - [{resource.title}]({resource.url}) ({resource.kind})")
                else:
                    lines.append(
                        f"- Continue **{item.canonical_name}** ({session_hours:g}h of {item.hours:g}h total) {citations}".rstrip()
                    )
            lines.append("")
    if plan and plan.deferred:
        lines.extend(["## Deferred items", ""])
        for deferred_gap in plan.deferred:
            citations = " ".join(
                f"[^{note_id}]" for note_id in provenance_by_skill.get(deferred_gap.skill_id, [])
            )
            lines.append(
                f"- **{deferred_gap.canonical_name}** ({deferred_gap.estimated_hours:g}h): {deferred_gap.reason} {citations}".rstrip()
            )
        lines.append("")
    if input_quality_notes:
        lines.extend(["## What to provide next", ""])
        if profile_record_count == 0:
            lines.append(
                "- Add coursework by course name, and describe projects or experience with the tools used, what you built, and your contribution."
            )
        if requirement_count == 0:
            lines.append(
                "- Paste the complete job description, enter its URL, or provide a specific role and company so requirements can be identified."
            )
        if state.degraded_reasons and profile_record_count > 0 and requirement_count > 0:
            lines.append("- Review the processing note above, correct the affected source, and rerun the analysis.")
        lines.append("")
    if provenance:
        lines.extend(["## Provenance appendix", ""])
        for record in provenance:
            quote = re.sub(r"\s+", " ", record["quote"])
            lines.append(
                f"[^{record['id']}]: `{record['source_doc_id']}` chars {record['char_start']}-{record['char_end']} "
                f"(confidence {record['extractor_confidence']:.2f}) - {quote}"
            )
    result = {
        "run_id": state.run_id,
        "role": job.role if job else state.role,
        "company": job.company if job else state.company,
        "discovery_tier": state.discovery_tier,
        "degraded": state.degraded,
        "degraded_reasons": state.degraded_reasons,
        "gaps": [gap.model_dump(mode="json") for gap in state.gaps],
        "plan": plan.model_dump(mode="json") if plan else None,
        "provenance": provenance,
        "traces": [trace.model_dump(mode="json") for trace in state.traces],
        "budget": state.budget_snapshot,
        "input_quality": {
            "status": input_quality_status,
            "profile_record_counts": profile_record_counts,
            "profile_record_count": profile_record_count,
            "job_requirement_count": requirement_count,
            "gap_count": len(state.gaps),
            "scheduled_item_count": len(plan_items),
            "deferred_item_count": len(plan.deferred) if plan else 0,
            "notes": input_quality_notes,
        },
    }
    return {"markdown": "\n".join(lines), "json": result, "pdf": _make_pdf("\n".join(lines))}


def _make_pdf(markdown: str) -> bytes:
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        LongTable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        TableStyle,
    )

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.68 * inch,
        leftMargin=0.68 * inch,
        topMargin=0.72 * inch,
        bottomMargin=0.68 * inch,
        title="PlacementGap learning plan",
        author="PlacementGap",
        subject="Evidence-grounded skills gap analysis and learning plan",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="PGTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22,
        leading=27, alignment=0, textColor=colors.HexColor("#25231f"), spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="PGHeading", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=15,
        leading=19, textColor=colors.HexColor("#25231f"), spaceBefore=12, spaceAfter=6, keepWithNext=1,
    ))
    styles.add(ParagraphStyle(
        name="PGSubheading", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=12,
        leading=16, textColor=colors.HexColor("#9d5e48"), spaceBefore=8, spaceAfter=4, keepWithNext=1,
    ))
    styles.add(ParagraphStyle(
        name="PGBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=10,
        leading=14, textColor=colors.HexColor("#37342f"), spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="PGTableHead", parent=styles["PGBody"], fontName="Helvetica-Bold", fontSize=9,
        leading=11, textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name="PGTableCell", parent=styles["PGBody"], fontSize=9, leading=12,
    ))
    styles.add(ParagraphStyle(
        name="PGProvenance", parent=styles["PGBody"], fontSize=8.5, leading=11,
        leftIndent=8, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="PGNestedBody", parent=styles["PGBody"], leftIndent=18, bulletIndent=8,
    ))

    def markup(value: str) -> str:
        substitutions: dict[str, str | int | None] = {
            "–": "-", "—": "-", "−": "-", "•": "-", "“": '"', "”": '"',
            "‘": "'", "’": "'", "…": "...",
        }
        value = value.translate(str.maketrans(substitutions))
        safe = escape(value, quote=False)
        safe = re.sub(
            r"\[([^\]]+)\]\((https?://[^ )]+)\)",
            r'<link href="\2" color="#496e5b">\1</link>',
            safe,
        )
        safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
        safe = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", safe)
        safe = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', safe)
        return re.sub(r"\[\^(\d+)\]", r"<super>\1</super>", safe)

    def cells(line: str) -> list[str]:
        return [value.strip().replace(r"\|", "|") for value in re.split(r"(?<!\\)\|", line.strip().strip("|"))]

    def is_separator(row: list[str]) -> bool:
        return bool(row) and all(re.fullmatch(r":?-{3,}:?", value.replace(" ", "")) for value in row)

    def draw_footer(canvas: Any, page_document: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#e4dfd5"))
        canvas.setLineWidth(0.5)
        canvas.line(page_document.leftMargin, 0.5 * inch, letter[0] - page_document.rightMargin, 0.5 * inch)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#817b70"))
        canvas.drawString(page_document.leftMargin, 0.34 * inch, "PLACEMENTGAP  /  EVIDENCE-GROUNDED CAREER PLANNING")
        canvas.drawRightString(letter[0] - page_document.rightMargin, 0.34 * inch, f"{page_document.page}")
        canvas.restoreState()

    story: list[Any] = []
    source_lines = markdown.splitlines()
    index = 0
    while index < len(source_lines):
        line = source_lines[index]
        if not line.strip():
            if not story or not (
                isinstance(story[-1], Paragraph)
                and story[-1].style.name in {"PGTitle", "PGHeading", "PGSubheading"}
            ):
                story.append(Spacer(1, 3))
            index += 1
            continue
        if line.startswith("|"):
            rows: list[list[str]] = []
            while index < len(source_lines) and source_lines[index].startswith("|"):
                rows.append(cells(source_lines[index]))
                index += 1
            if len(rows) > 1 and is_separator(rows[1]):
                rows.pop(1)
            column_count = max((len(row) for row in rows), default=0)
            if column_count:
                table_rows = []
                for row_index, row in enumerate(rows):
                    row = (row + [""] * column_count)[:column_count]
                    paragraph_style = styles["PGTableHead"] if row_index == 0 else styles["PGTableCell"]
                    table_rows.append([Paragraph(markup(value), paragraph_style) for value in row])
                widths = [1.15 * inch, 3.95 * inch, 1.05 * inch, 0.85 * inch]
                if column_count != 4:
                    widths = [document.width / column_count] * column_count
                table = LongTable(table_rows, colWidths=widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#343c34")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fbfaf7"), colors.HexColor("#f2efe8")]),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#ded9cf")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                story.extend([table, Spacer(1, 5)])
            continue
        if line.startswith("# "):
            style = styles["PGTitle"]
            value = line[2:]
            story.append(Paragraph(markup(value), style))
        elif line.startswith("## "):
            value = line[3:]
            story.append(Paragraph(markup(value), styles["PGHeading"]))
        elif line.startswith("### "):
            value = line[4:]
            story.append(Paragraph(markup(value), styles["PGSubheading"]))
        elif line.startswith("- "):
            story.append(Paragraph(markup(line[2:]), styles["PGBody"], bulletText="-"))
        elif line.startswith("  - "):
            story.append(Paragraph(markup(line[4:]), styles["PGNestedBody"], bulletText="-"))
        elif line.startswith("[^"):
            story.append(Paragraph(markup(line), styles["PGProvenance"]))
        else:
            story.append(Paragraph(markup(line), styles["PGBody"]))
        if not line.startswith(("# ", "## ", "### ")):
            story.append(Spacer(1, 1))
        index += 1
    document.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return output.getvalue()
