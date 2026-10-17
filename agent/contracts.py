from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SkillLevel(StrEnum):
    aware = "aware"
    can_use = "can_use"
    can_build = "can_build"
    can_design = "can_design"

    @property
    def rank(self) -> int:
        return list(SkillLevel).index(self)


class GapVerdict(StrEnum):
    has = "has"
    partial = "partial"
    missing = "missing"


class SourceSpan(Contract):
    source_doc_id: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    extractor_confidence: float = Field(ge=0, le=1)
    quote: str = ""

    @model_validator(mode="after")
    def valid_range(self) -> SourceSpan:
        if self.char_end < self.char_start:
            raise ValueError("char_end must be >= char_start")
        return self


class Evidence(Contract):
    skill_id: str
    level: SkillLevel
    span: SourceSpan
    evidence_type: str = "profile"
    explanation: str = ""


class RequirementSpec(Contract):
    skill_text: str
    hard_requirement: bool = True
    required_level: SkillLevel = SkillLevel.can_use
    years_hint: float | None = Field(default=None, ge=0, le=80)
    span: SourceSpan
    skill_id: str | None = None
    canonical_name: str | None = None
    canonical_confidence: float = Field(default=0, ge=0, le=1)
    canonical_method: str = "UNRESOLVED"
    market_demand_weight: float = Field(default=0.5, ge=0, le=1)


class CourseRecord(Contract):
    name: str
    description: str = ""
    grade: str | None = None
    skills: list[str] = Field(default_factory=list)
    span: SourceSpan


class ProjectRecord(Contract):
    name: str
    description: str
    artifacts: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    design_ownership: bool = False
    span: SourceSpan


class ExperienceRecord(Contract):
    title: str
    organization: str = ""
    description: str = ""
    skills: list[str] = Field(default_factory=list)
    span: SourceSpan


class StudentProfile(Contract):
    student_id: str
    source_doc_id: str
    raw_text: str
    courses: list[CourseRecord] = Field(default_factory=list)
    projects: list[ProjectRecord] = Field(default_factory=list)
    experiences: list[ExperienceRecord] = Field(default_factory=list)
    demonstrated_skills: dict[str, SkillLevel] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    parser_tier: str = "text"
    degraded: bool = False
    degraded_reason: str | None = None


class JobDescription(Contract):
    source_doc_id: str
    role: str
    company: str | None = None
    text: str
    discovery_tier: str
    content_hash: str
    requirements: list[RequirementSpec] = Field(default_factory=list)
    degraded: bool = False
    degraded_reason: str | None = None


class Gap(Contract):
    skill_id: str
    canonical_name: str
    required_level: SkillLevel
    demonstrated_level: SkillLevel
    verdict: GapVerdict
    level_delta: int = Field(ge=0, le=3)
    effort_hours: float = Field(default=4, gt=0)
    priority_score: float = Field(default=0, ge=0)
    hard_requirement: bool = True
    market_demand_weight: float = Field(default=0.5, ge=0, le=1)
    prerequisite_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    rationale: str


class Resource(Contract):
    title: str
    url: str
    kind: str = "documentation"
    estimated_cost_usd: float = Field(default=0, ge=0)
    checked_at: str | None = None
    relevance: float = Field(default=0.5, ge=0, le=1)


class PlanItem(Contract):
    skill_id: str
    canonical_name: str
    week: int = Field(ge=1)
    hours: float = Field(gt=0)
    weekly_hours: dict[int, float] = Field(default_factory=dict)
    outcome: str
    prerequisite_ids: list[str] = Field(default_factory=list)
    resources: list[Resource] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class PlanWeek(Contract):
    week: int = Field(ge=1)
    capacity_hours: float = Field(gt=0)
    scheduled_hours: float = Field(ge=0)
    items: list[PlanItem] = Field(default_factory=list)


class DeferredGap(Contract):
    skill_id: str
    canonical_name: str
    reason: str
    estimated_hours: float = Field(gt=0)


class Plan(Contract):
    weeks: list[PlanWeek] = Field(default_factory=list)
    deferred: list[DeferredGap] = Field(default_factory=list)
    satisfied_skills: list[str] = Field(default_factory=list)
    total_hours: float = Field(default=0, ge=0)
    total_budget_hours: float = Field(default=0, ge=0)
    violations: list[str] = Field(default_factory=list)
    solver_parameters: dict[str, Any] = Field(default_factory=dict)


class PlanRequest(Contract):
    gaps: list[Gap]
    weeks: int = Field(ge=1, le=104)
    hours_per_week: float = Field(gt=0, le=100)
    resources_by_skill: dict[str, list[Resource]] = Field(default_factory=dict)
    critique_adjustments: dict[str, float] = Field(default_factory=dict)
    forced_deferred: dict[str, str] = Field(default_factory=dict)


class CritiqueItem(Contract):
    category: str
    skill_id: str | None = None
    concern: str
    adjustment: str
    parameter: str
    delta: float = 0
    severity: str = "medium"


class TraceRow(Contract):
    run_id: str
    node_name: str
    call_type: str
    model: str
    prompt_version: str
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    cache_hit: bool = False
    timestamp: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunState(Contract):
    run_id: str
    student_id: str
    profile_text: str
    profile_filename: str | None = None
    profile_file_base64: str | None = None
    jd_text: str = ""
    jd_url: str | None = None
    role: str = ""
    company: str | None = None
    weeks: int = 8
    hours_per_week: float = 8
    max_cost_usd: float = 1.0
    max_tokens: int = 40_000
    request_id: str | None = None
    source_doc_id: str = ""
    profile: StudentProfile | None = None
    job: JobDescription | None = None
    gaps: list[Gap] = Field(default_factory=list)
    plan: Plan | None = None
    critiques: list[CritiqueItem] = Field(default_factory=list)
    unresolved_critiques: list[CritiqueItem] = Field(default_factory=list)
    critique_iteration: int = 0
    approved: bool = False
    approval_note: str | None = None
    plan_edits: dict[str, Any] = Field(default_factory=dict)
    status: str = "queued"
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)
    discovery_tier: str = ""
    traces: list[TraceRow] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    report_markdown: str | None = None
    report_json: dict[str, Any] | None = None
    report_pdf: bytes | None = None
    budget_snapshot: dict[str, Any] = Field(default_factory=dict)

    @field_validator("profile_text", "jd_text")
    @classmethod
    def limit_untrusted_text(cls, value: str) -> str:
        if len(value) > 500_000:
            raise ValueError("Input exceeds the 500,000 character limit")
        return value
