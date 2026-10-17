from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


def _set_test_auth_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PLACEMENTGAP_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("PLACEMENTGAP_AUTH_SECRET_FILE", str(tmp_path / "auth.secret"))
    monkeypatch.setenv("PLACEMENTGAP_RUN_DB", str(tmp_path / "runs.sqlite3"))
    monkeypatch.setenv("PLACEMENTGAP_RUN_FILES", str(tmp_path / "runs"))
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)


@pytest.mark.asyncio
async def test_workspace_is_private_persistent_and_strict(tmp_path, monkeypatch) -> None:
    _set_test_auth_environment(monkeypatch, tmp_path)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        denied = await client.get("/workspace")
        assert denied.status_code == 401

        signup = await client.post("/auth/signup", json={
            "full_name": "Jordan Lee",
            "email": "workspace@example.com",
            "phone": "+1 202 555 0101",
            "password": "first-password-123",
        })
        await client.post("/auth/verify", json={
            "challenge_id": signup.json()["challenge_id"],
            "code": signup.json()["development_code"],
        })

        payload = {
            "saved_roles": [{
                "id": "role-1", "title": "Backend Engineer", "company": "Example",
                "location": "Remote", "url": "https://example.com/jobs/backend",
                "description": "Python and APIs", "run_id": None,
                "gaps": [], "created_at": "2026-10-17T00:00:00Z",
            }],
            "roadmap": {"completed_task_ids": ["week-1-python"], "minutes_by_task": {"week-1-python": 45}},
            "skill_checks": [{"id": "check-1", "skill_id": "python", "skill_name": "Python", "correct": 2, "total": 3, "confidence": 3, "completed_at": "2026-10-17T00:00:00Z"}],
            "projects": [{"id": "project-1", "title": "API project", "brief": "Build and test an API.", "skill_ids": ["python"], "tasks": [{"id": "task-1", "label": "Add tests", "completed": True}], "created_at": "2026-10-17T00:00:00Z"}],
            "artifacts": [{"id": "artifact-1", "kind": "repository", "title": "API repository", "url": "https://github.com/example/api", "description": "Documented API", "skill_ids": ["python"], "added_at": "2026-10-17T00:00:00Z", "quality_checks": {"goal_clear": True, "setup_present": True, "tests_present": True, "ownership_clear": True, "link_verified": True}}],
            "applications": [{"id": "application-1", "company": "Example", "role": "Backend Engineer", "job_url": "https://example.com/jobs/backend", "status": "applied", "deadline": "2026-11-01", "notes": "Recruiter follow-up", "run_id": None, "created_at": "2026-10-17T00:00:00Z"}],
            "application_packs": [{"id": "pack-1", "role": "Backend Engineer", "company": "Example", "resume_bullets": ["Built a source-backed API"], "cover_letter": "Draft for review", "talking_points": ["Explain testing"], "created_at": "2026-10-17T00:00:00Z"}],
            "interview_sessions": [{"id": "interview-1", "role": "Backend Engineer", "answers": [{"prompt": "Describe the project.", "answer": "I built and tested the API.", "self_rating": 4}], "completed_at": "2026-10-17T00:00:00Z"}],
        }
        saved = await client.put("/workspace", json=payload)
        assert saved.status_code == 200
        assert saved.json()["saved_roles"][0]["title"] == "Backend Engineer"
        loaded = await client.get("/workspace")
        assert loaded.status_code == 200
        assert loaded.json() == saved.json()

        invalid = await client.put("/workspace", json={**payload, "unknown": True})
        assert invalid.status_code == 422
        bad_link = {**payload, "saved_roles": [{**payload["saved_roles"][0], "url": "javascript:alert(1)"}]}
        assert (await client.put("/workspace", json=bad_link)).status_code == 422

        await client.post("/auth/logout")
        assert (await client.get("/workspace")).status_code == 401
