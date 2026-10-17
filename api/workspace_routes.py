from __future__ import annotations

import asyncio
from typing import Literal, cast
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.auth_routes import authenticated_user
from api.auth_store import AuthStore

router = APIRouter(prefix="/workspace", tags=["student workspace"])


class WorkspaceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GapSnapshot(WorkspaceModel):
    skill_id: str = Field(min_length=1, max_length=120)
    canonical_name: str = Field(min_length=1, max_length=160)
    verdict: Literal["has", "partial", "missing"]
    level_delta: int = Field(ge=0, le=3)
    priority_score: float = Field(ge=0, le=100_000)


class SavedRole(WorkspaceModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    company: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=120)
    url: str = Field(default="", max_length=2_048)
    description: str = Field(default="", max_length=12_000)
    run_id: str | None = Field(default=None, max_length=80)
    gaps: list[GapSnapshot] = Field(default_factory=list, max_length=100)
    created_at: str = Field(min_length=10, max_length=40)

    @field_validator("url")
    @classmethod
    def require_job_url(cls, value: str) -> str:
        if value and (urlsplit(value).scheme not in {"http", "https"} or not urlsplit(value).netloc):
            raise ValueError("Job links must be complete HTTP or HTTPS URLs.")
        return value


class RoadmapProgress(WorkspaceModel):
    completed_task_ids: list[str] = Field(default_factory=list, max_length=500)
    minutes_by_task: dict[str, int] = Field(default_factory=dict, max_length=500)


class SkillCheck(WorkspaceModel):
    id: str = Field(min_length=1, max_length=80)
    skill_id: str = Field(min_length=1, max_length=120)
    skill_name: str = Field(min_length=1, max_length=160)
    correct: int = Field(ge=0, le=100)
    total: int = Field(ge=1, le=100)
    confidence: int = Field(ge=1, le=5)
    completed_at: str = Field(min_length=10, max_length=40)


class ProjectTask(WorkspaceModel):
    id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=300)
    completed: bool = False


class ProjectTrack(WorkspaceModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=180)
    brief: str = Field(min_length=1, max_length=3_000)
    skill_ids: list[str] = Field(default_factory=list, max_length=20)
    tasks: list[ProjectTask] = Field(default_factory=list, max_length=40)
    created_at: str = Field(min_length=10, max_length=40)


class ArtifactQualityCheck(WorkspaceModel):
    goal_clear: bool = False
    setup_present: bool = False
    tests_present: bool = False
    ownership_clear: bool = False
    link_verified: bool = False


class PortfolioArtifact(WorkspaceModel):
    id: str = Field(min_length=1, max_length=80)
    kind: Literal["repository", "deployed_project", "certificate", "writeup", "other"]
    title: str = Field(min_length=1, max_length=180)
    url: str = Field(default="", max_length=2_048)
    description: str = Field(default="", max_length=2_000)
    skill_ids: list[str] = Field(default_factory=list, max_length=30)
    added_at: str = Field(min_length=10, max_length=40)
    quality_checks: ArtifactQualityCheck = Field(default_factory=lambda: ArtifactQualityCheck())

    @field_validator("url")
    @classmethod
    def require_web_url(cls, value: str) -> str:
        if value and (urlsplit(value).scheme not in {"http", "https"} or not urlsplit(value).netloc):
            raise ValueError("Artifact links must be complete HTTP or HTTPS URLs.")
        return value


class Application(WorkspaceModel):
    id: str = Field(min_length=1, max_length=80)
    company: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=120)
    job_url: str = Field(default="", max_length=2_048)
    status: Literal["saved", "applied", "screen", "interview", "offer", "rejected"] = "saved"
    deadline: str = Field(default="", max_length=10)
    notes: str = Field(default="", max_length=3_000)
    run_id: str | None = Field(default=None, max_length=80)
    created_at: str = Field(min_length=10, max_length=40)

    @field_validator("job_url")
    @classmethod
    def require_job_url(cls, value: str) -> str:
        if value and (urlsplit(value).scheme not in {"http", "https"} or not urlsplit(value).netloc):
            raise ValueError("Job links must be complete HTTP or HTTPS URLs.")
        return value


class ApplicationPack(WorkspaceModel):
    id: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    company: str = Field(default="", max_length=120)
    resume_bullets: list[str] = Field(default_factory=list, max_length=20)
    cover_letter: str = Field(default="", max_length=8_000)
    talking_points: list[str] = Field(default_factory=list, max_length=20)
    created_at: str = Field(min_length=10, max_length=40)


class InterviewAnswer(WorkspaceModel):
    prompt: str = Field(min_length=1, max_length=1_000)
    answer: str = Field(default="", max_length=5_000)
    self_rating: int = Field(default=3, ge=1, le=5)


class InterviewSession(WorkspaceModel):
    id: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=120)
    answers: list[InterviewAnswer] = Field(default_factory=list, max_length=30)
    completed_at: str = Field(min_length=10, max_length=40)


class WorkspacePayload(WorkspaceModel):
    saved_roles: list[SavedRole] = Field(default_factory=list, max_length=30)
    roadmap: RoadmapProgress = Field(default_factory=RoadmapProgress)
    skill_checks: list[SkillCheck] = Field(default_factory=list, max_length=200)
    projects: list[ProjectTrack] = Field(default_factory=list, max_length=100)
    artifacts: list[PortfolioArtifact] = Field(default_factory=list, max_length=100)
    applications: list[Application] = Field(default_factory=list, max_length=100)
    application_packs: list[ApplicationPack] = Field(default_factory=list, max_length=25)
    interview_sessions: list[InterviewSession] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def enforce_payload_size(self) -> WorkspacePayload:
        if len(self.model_dump_json().encode("utf-8")) > 400_000:
            raise ValueError("Workspace data exceeds the 400 KB limit.")
        return self


def _store(request: Request) -> AuthStore:
    return cast(AuthStore, request.app.state.auth_store)


@router.get("", response_model=WorkspacePayload)
async def read_workspace(request: Request) -> WorkspacePayload:
    user = await authenticated_user(request)
    stored = await asyncio.to_thread(_store(request).get_workspace, str(user["id"]))
    return WorkspacePayload.model_validate(stored or {})


@router.put("", response_model=WorkspacePayload)
async def write_workspace(payload: WorkspacePayload, request: Request) -> WorkspacePayload:
    user = await authenticated_user(request)
    try:
        saved = await asyncio.to_thread(
            _store(request).save_workspace, str(user["id"]), payload.model_dump(mode="json")
        )
    except ValueError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    return WorkspacePayload.model_validate(saved)
