from __future__ import annotations

from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient

from api.auth_routes import _hash_password, _verify_password
from api.main import app


def test_password_hash_is_salted_and_verifiable() -> None:
    first = _hash_password("correct-horse-battery-staple")
    second = _hash_password("correct-horse-battery-staple")
    assert first != second
    assert _verify_password("correct-horse-battery-staple", first)
    assert not _verify_password("incorrect-password", first)


@pytest.mark.asyncio
async def test_signup_verify_reset_login_and_logout(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PLACEMENTGAP_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("PLACEMENTGAP_AUTH_SECRET_FILE", str(tmp_path / "auth.secret"))
    monkeypatch.setenv("PLACEMENTGAP_RUN_DB", str(tmp_path / "runs.sqlite3"))
    monkeypatch.setenv("PLACEMENTGAP_RUN_FILES", str(tmp_path / "runs"))
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    for provider in ("GOOGLE", "MICROSOFT", "GITHUB"):
        monkeypatch.delenv(f"{provider}_CLIENT_ID", raising=False)
        monkeypatch.delenv(f"{provider}_CLIENT_SECRET", raising=False)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
            providers = await client.get("/auth/providers")
            assert providers.json()["providers"] == {"google": False, "microsoft": False, "github": False}
            unauthenticated = await client.get("/auth/me")
            assert unauthenticated.status_code == 401
            protected_run = await client.post("/runs", json={
                "profile_text": "BSc computer science, Python projects",
                "jd_text": "Software Engineer with Python",
            })
            assert protected_run.status_code == 401

            signup = await client.post("/auth/signup", json={
                "full_name": "Jordan Lee",
                "email": "jordan@example.com",
                "phone": "+1 202 555 0101",
                "password": "first-password-123",
            })
            assert signup.status_code == 200
            challenge = signup.json()
            assert challenge["delivery_mode"] == "local_development"
            verified = await client.post("/auth/verify", json={
                "challenge_id": challenge["challenge_id"], "code": challenge["development_code"],
            })
            assert verified.status_code == 200
            assert verified.json()["user"]["full_name"] == "Jordan Lee"
            assert (await client.get("/auth/me")).status_code == 200

            reset = await client.post("/auth/forgot", json={"email": "jordan@example.com"})
            assert reset.status_code == 200
            reset_challenge = reset.json()
            changed = await client.post("/auth/reset", json={
                "challenge_id": reset_challenge["challenge_id"],
                "code": reset_challenge["development_code"],
                "new_password": "second-password-456",
            })
            assert changed.status_code == 200
            await client.post("/auth/logout")
            assert (await client.get("/auth/me")).status_code == 401
            login_code = await client.post("/auth/login-code", json={"email": "jordan@example.com"})
            assert login_code.status_code == 200
            login_challenge = login_code.json()
            assert login_challenge["delivery_mode"] == "local_development"
            verified_login = await client.post("/auth/login-verify", json={
                "challenge_id": login_challenge["challenge_id"],
                "code": login_challenge["development_code"],
            })
            assert verified_login.status_code == 200
            assert verified_login.json()["user"]["email"] == "jordan@example.com"
            assert (await client.get("/auth/me")).status_code == 200
            await client.post("/auth/logout")
            decoy_code = await client.post("/auth/login-code", json={"email": "unknown@example.com"})
            assert decoy_code.status_code == 200
            assert decoy_code.json()["message"] == login_challenge["message"]
            decoy_verify = await client.post("/auth/login-verify", json={
                "challenge_id": decoy_code.json()["challenge_id"],
                "code": decoy_code.json()["development_code"],
            })
            assert decoy_verify.status_code == 401
            logged_in = await client.post("/auth/login", json={
                "email": "jordan@example.com", "password": "second-password-456",
            })
            assert logged_in.status_code == 200
            rejected = await client.post("/auth/login", json={
                "email": "jordan@example.com", "password": "first-password-123",
            })
            assert rejected.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["google", "microsoft", "github"])
async def test_oauth_start_uses_provider_credentials_and_local_callback(provider, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PLACEMENTGAP_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("PLACEMENTGAP_AUTH_SECRET_FILE", str(tmp_path / "auth.secret"))
    monkeypatch.setenv("PLACEMENTGAP_RUN_DB", str(tmp_path / "runs.sqlite3"))
    monkeypatch.setenv("PLACEMENTGAP_RUN_FILES", str(tmp_path / "runs"))
    monkeypatch.setenv("FRONTEND_URL", "http://127.0.0.1:5173")
    monkeypatch.setenv("OAUTH_REDIRECT_BASE", "http://127.0.0.1:8000")
    monkeypatch.setenv("MICROSOFT_FRONTEND_URL", "http://127.0.0.1:5173")
    monkeypatch.setenv("MICROSOFT_REDIRECT_BASE", "http://127.0.0.1:8000")
    prefix = provider.upper()
    monkeypatch.setenv(f"{prefix}_CLIENT_ID", f"{provider}-client-id")
    monkeypatch.setenv(f"{prefix}_CLIENT_SECRET", "test-secret")
    monkeypatch.delenv("MICROSOFT_TENANT_ID", raising=False)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        providers = await client.get("/auth/providers")
        assert providers.json()["providers"][provider] is True
        response = await client.get(f"/auth/{provider}/start", follow_redirects=False)
        assert response.status_code == 302
        query = parse_qs(urlparse(response.headers["location"]).query)
        assert query["client_id"] == [f"{provider}-client-id"]
        callback_base = "http://127.0.0.1:8000"
        assert query["redirect_uri"] == [f"{callback_base}/auth/{provider}/callback"]
        if provider == "microsoft":
            cancelled = await client.get(
                "/auth/microsoft/callback?error=access_denied", follow_redirects=False
            )
            assert cancelled.headers["location"] == "http://127.0.0.1:5173/?auth_error=provider_cancelled"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "frontend"),
    [
        ("google", "http://127.0.0.1:5173"),
        ("microsoft", "http://127.0.0.1:5173"),
    ],
)
async def test_oauth_callback_creates_session_for_google_and_microsoft(
    provider, frontend, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("PLACEMENTGAP_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    monkeypatch.setenv("PLACEMENTGAP_AUTH_SECRET_FILE", str(tmp_path / "auth.secret"))
    monkeypatch.setenv("PLACEMENTGAP_RUN_DB", str(tmp_path / "runs.sqlite3"))
    monkeypatch.setenv("PLACEMENTGAP_RUN_FILES", str(tmp_path / "runs"))
    monkeypatch.setenv("FRONTEND_URL", "http://127.0.0.1:5173")
    monkeypatch.setenv("OAUTH_REDIRECT_BASE", "http://127.0.0.1:8000")
    monkeypatch.setenv("MICROSOFT_FRONTEND_URL", "http://127.0.0.1:5173")
    monkeypatch.setenv("MICROSOFT_REDIRECT_BASE", "http://127.0.0.1:8000")
    prefix = provider.upper()
    monkeypatch.setenv(f"{prefix}_CLIENT_ID", f"{provider}-client-id")
    monkeypatch.setenv(f"{prefix}_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(
        "api.auth_routes._oauth_identity",
        AsyncMock(return_value=(f"{provider}@example.test", "Jordan Lee")),
    )

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        start = await client.get(f"/auth/{provider}/start", follow_redirects=False)
        state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
        callback = await client.get(
            f"/auth/{provider}/callback",
            params={"code": "recorded-code", "state": state},
            follow_redirects=False,
        )

        assert callback.status_code == 303
        assert callback.headers["location"] == f"{frontend}/auth/callback"
        assert (await client.get("/auth/me")).json()["user"]["email"] == f"{provider}@example.test"
