from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
import smtplib
import ssl
import urllib.parse
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Literal, cast

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.auth_store import AuthStore

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)
SESSION_COOKIE = "placementgap_session"
SESSION_SECONDS = 30 * 24 * 60 * 60
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9 ().-]{6,22}$")


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    phone: str = Field(min_length=7, max_length=24)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Enter your full name.")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str) -> str:
        value = value.strip()
        if not PHONE_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid phone number, including country code if needed.")
        return value


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid email address.")
        return value


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    challenge_id: str = Field(min_length=24, max_length=80)
    code: str = Field(pattern=r"^[0-9]{6}$")


class ResetRequest(VerifyRequest):
    new_password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid email address.")
        return value


def _store(request: Request) -> AuthStore:
    return cast(AuthStore, request.app.state.auth_store)


def _secret(request: Request) -> bytes:
    return cast(bytes, request.app.state.auth_secret)


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${derived.hex()}"


def _verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        computed = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(computed.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


_DUMMY_PASSWORD_HASH = _hash_password("PlacementGap-invalid-login-timing-padding")


def _code_hash(request: Request, challenge_id: str, code: str) -> str:
    return hmac.new(
        _secret(request), f"{challenge_id}:{code}".encode(), hashlib.sha256
    ).hexdigest()


def _public_user(user: dict[str, Any]) -> dict[str, str | None]:
    return {
        "id": str(user["id"]),
        "full_name": str(user["full_name"]),
        "email": str(user["email"]),
        "phone": str(user["phone"]) if user.get("phone") else None,
    }


async def authenticated_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    user = await asyncio.to_thread(_store(request).get_user_by_session, token)
    if not user:
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.")
    return user


def _set_session(
    response: Response, request: Request, user: dict[str, Any], provider: str | None = None
) -> None:
    token = _store(request).create_session(str(user["id"]))
    public_url = (
        os.getenv("MICROSOFT_REDIRECT_BASE", "http://127.0.0.1:8000")
        if provider == "microsoft"
        else os.getenv("OAUTH_REDIRECT_BASE", "http://127.0.0.1:8000")
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=public_url.startswith("https://"),
        samesite="lax",
        path="/",
    )


def _auth_secret() -> bytes:
    configured = os.getenv("AUTH_SECRET")
    if configured:
        if len(configured.encode("utf-8")) < 32:
            raise RuntimeError("AUTH_SECRET must contain at least 32 bytes.")
        return configured.encode("utf-8")
    if os.getenv("APP_ENV", "development").lower() == "production":
        raise RuntimeError("Set AUTH_SECRET before starting PlacementGap in production.")
    path = Path(os.getenv("PLACEMENTGAP_AUTH_SECRET_FILE", "./data/auth.secret"))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as secret_file:
            secret_file.write(secrets.token_bytes(48))
    except FileExistsError:
        pass
    return path.read_bytes()


def _send_email_code(email: str, code: str, purpose: str) -> None:
    host = os.getenv("SMTP_HOST")
    if not host:
        if os.getenv("APP_ENV", "development").lower() == "production":
            raise RuntimeError("Email verification requires SMTP_HOST in production.")
        return
    sender = os.getenv("SMTP_FROM")
    if not sender:
        raise RuntimeError("Set SMTP_FROM to deliver verification emails.")
    message = EmailMessage()
    message["Subject"] = "Your PlacementGap verification code"
    message["From"] = sender
    message["To"] = email
    action = {
        "signup": "finish creating your account",
        "reset": "reset your password",
        "login": "sign in to your PlacementGap account",
    }.get(purpose, "verify your PlacementGap account")
    message.set_content(
        f"Use this 6-digit code to {action}: {code}\n\n"
        "This code expires in 10 minutes. If you did not request it, you can ignore this email."
    )
    port = int(os.getenv("SMTP_PORT", "587"))
    timeout = 12
    if os.getenv("SMTP_USE_SSL", "false").lower() == "true":
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context()) as smtp:
            _smtp_login_and_send(smtp, message)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            _smtp_login_and_send(smtp, message)


def _smtp_login_and_send(smtp: smtplib.SMTP, message: EmailMessage) -> None:
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    if username and password:
        smtp.login(username, password)
    smtp.send_message(message)


async def _issue_code(
    request: Request, email: str, purpose: Literal["signup", "reset", "login"], payload: dict[str, Any] | None = None
) -> dict[str, str]:
    challenge_id = secrets.token_urlsafe(24)
    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        await asyncio.to_thread(
            _store(request).create_challenge,
            challenge_id=challenge_id,
            email=email,
            purpose=purpose,
            code_hash=_code_hash(request, challenge_id, code),
            payload=payload,
        )
    except ValueError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    try:
        await asyncio.to_thread(_send_email_code, email, code, purpose)
    except Exception as error:
        await asyncio.to_thread(_store(request).consume_challenge, challenge_id)
        raise HTTPException(status_code=503, detail="Email delivery is unavailable. Check SMTP configuration.") from error
    message = (
        "If an account exists for this address, a sign-in code has been sent."
        if purpose == "login"
        else "Verification code sent. It expires in 10 minutes."
    )
    result = {"challenge_id": challenge_id, "message": message}
    if not os.getenv("SMTP_HOST") and os.getenv("APP_ENV", "development").lower() != "production":
        result["development_code"] = code
        result["delivery_mode"] = "local_development"
    return result


async def _issue_decoy_login_code(request: Request, email: str) -> dict[str, str]:
    """Create a non-authenticating challenge to keep login responses uniform."""
    challenge_id = secrets.token_urlsafe(24)
    code = f"{secrets.randbelow(1_000_000):06d}"
    try:
        await asyncio.to_thread(
            _store(request).create_challenge,
            challenge_id=challenge_id,
            email=email,
            purpose="login",
            code_hash=_code_hash(request, challenge_id, code),
            payload={"eligible": False},
        )
    except ValueError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    result = {
        "challenge_id": challenge_id,
        "message": "If an account exists for this address, a sign-in code has been sent.",
    }
    if not os.getenv("SMTP_HOST") and os.getenv("APP_ENV", "development").lower() != "production":
        result["development_code"] = code
        result["delivery_mode"] = "local_development"
    return result


@router.post("/signup")
async def signup(body: SignupRequest, request: Request) -> dict[str, str]:
    store = _store(request)
    existing = await asyncio.to_thread(store.get_user_by_email, body.email)
    if existing:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    payload = {
        "full_name": body.full_name,
        "phone": body.phone,
        "password_hash": _hash_password(body.password),
    }
    return await _issue_code(request, body.email, "signup", payload)


@router.post("/verify")
async def verify_signup(body: VerifyRequest, request: Request, response: Response) -> dict[str, Any]:
    store = _store(request)
    challenge = await asyncio.to_thread(
        store.verify_challenge, body.challenge_id, _code_hash(request, body.challenge_id, body.code), "signup"
    )
    if not challenge:
        raise HTTPException(status_code=400, detail="That code is invalid, expired, or already used.")
    payload = challenge["payload"]
    try:
        user = await asyncio.to_thread(
            store.create_user,
            email=str(challenge["email"]),
            full_name=str(payload["full_name"]),
            phone=str(payload["phone"]),
            password_hash=str(payload["password_hash"]),
        )
    except Exception as error:
        await asyncio.to_thread(store.consume_challenge, body.challenge_id)
        raise HTTPException(status_code=409, detail="An account already uses that email or phone number.") from error
    _set_session(response, request, user)
    return {"user": _public_user(user)}


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    store = _store(request)
    client_ip = request.client.host if request.client else "unknown"
    if await asyncio.to_thread(store.login_rate_limited, body.email, client_ip):
        raise HTTPException(status_code=429, detail="Too many unsuccessful attempts. Wait 15 minutes and try again.")
    user = await asyncio.to_thread(store.get_user_by_email, body.email)
    valid = _verify_password(body.password, (user.get("password_hash") or _DUMMY_PASSWORD_HASH) if user else _DUMMY_PASSWORD_HASH)
    await asyncio.to_thread(store.record_login_attempt, body.email, client_ip, bool(user and valid))
    if not user or not valid:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    _set_session(response, request, user)
    return {"user": _public_user(user)}


@router.post("/login-code")
async def request_login_code(body: EmailRequest, request: Request) -> dict[str, str]:
    user = await asyncio.to_thread(_store(request).get_user_by_email, body.email)
    if not user:
        return await _issue_decoy_login_code(request, body.email)
    try:
        return await _issue_code(request, body.email, "login", {"eligible": True})
    except HTTPException as error:
        if error.status_code != 503:
            raise
        return await _issue_decoy_login_code(request, body.email)


@router.post("/login-verify")
async def verify_login_code(body: VerifyRequest, request: Request, response: Response) -> dict[str, Any]:
    store = _store(request)
    challenge = await asyncio.to_thread(
        store.verify_challenge, body.challenge_id, _code_hash(request, body.challenge_id, body.code), "login"
    )
    if not challenge or not challenge["payload"].get("eligible"):
        raise HTTPException(status_code=401, detail="That code is invalid, expired, or cannot sign in to this account.")
    user = await asyncio.to_thread(store.get_user_by_email, str(challenge["email"]))
    if not user:
        raise HTTPException(status_code=401, detail="That code is invalid, expired, or cannot sign in to this account.")
    _set_session(response, request, user)
    return {"user": _public_user(user)}


@router.post("/forgot")
async def forgot_password(body: EmailRequest, request: Request) -> dict[str, str]:
    store = _store(request)
    user = await asyncio.to_thread(store.get_user_by_email, body.email)
    if user:
        return await _issue_code(request, body.email, "reset")
    return {"message": "If an account exists for this address, a reset code has been sent."}


@router.post("/reset")
async def reset_password(body: ResetRequest, request: Request, response: Response) -> dict[str, Any]:
    store = _store(request)
    challenge = await asyncio.to_thread(
        store.verify_challenge, body.challenge_id, _code_hash(request, body.challenge_id, body.code), "reset"
    )
    if not challenge:
        raise HTTPException(status_code=400, detail="That code is invalid, expired, or already used.")
    user = await asyncio.to_thread(
        store.get_user_by_email, str(challenge["email"])
    )
    if not user:
        raise HTTPException(status_code=400, detail="That reset request is no longer valid.")
    await asyncio.to_thread(store.update_password, str(challenge["email"]), _hash_password(body.new_password))
    await asyncio.to_thread(store.consume_challenge, body.challenge_id)
    _set_session(response, request, user)
    return {"user": _public_user(user)}


@router.get("/me")
async def me(request: Request) -> dict[str, Any]:
    user = await authenticated_user(request)
    return {"user": _public_user(user)}


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await asyncio.to_thread(_store(request).revoke_session, token)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
    return {"message": "Signed out."}


def _provider_config(provider: str) -> dict[str, str]:
    if provider not in {"google", "microsoft", "github"}:
        raise HTTPException(status_code=404, detail="Sign-in provider is not supported.")
    prefix = provider.upper()
    client_id = os.getenv(f"{prefix}_CLIENT_ID")
    client_secret = os.getenv(f"{prefix}_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail=f"{provider.title()} sign-in is not configured yet. Add {prefix}_CLIENT_ID and {prefix}_CLIENT_SECRET.",
        )
    base = (
        os.getenv("MICROSOFT_REDIRECT_BASE", "http://127.0.0.1:8000")
        if provider == "microsoft"
        else os.getenv("OAUTH_REDIRECT_BASE", "http://127.0.0.1:8000")
    ).rstrip("/")
    callback = f"{base}/auth/{provider}/callback"
    if provider == "google":
        authorize = "https://accounts.google.com/o/oauth2/v2/auth"
        token = "https://oauth2.googleapis.com/token"
        scope = "openid email profile"
    elif provider == "microsoft":
        tenant = os.getenv("MICROSOFT_TENANT_ID", "common")
        authorize = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
        token = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        scope = "openid profile email User.Read"
    else:
        authorize = "https://github.com/login/oauth/authorize"
        token = "https://github.com/login/oauth/access_token"
        scope = "read:user user:email"
    return {"client_id": client_id, "client_secret": client_secret, "callback": callback,
            "authorize": authorize, "token": token, "scope": scope}


@router.get("/providers")
async def providers() -> dict[str, dict[str, bool]]:
    return {
        "providers": {
            name: bool(os.getenv(f"{name.upper()}_CLIENT_ID") and os.getenv(f"{name.upper()}_CLIENT_SECRET"))
            for name in ("google", "microsoft", "github")
        }
    }


@router.get("/{provider}/start")
async def oauth_start(provider: str, request: Request) -> RedirectResponse:
    config = _provider_config(provider)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    await asyncio.to_thread(_store(request).save_oauth_state, _store(request).token_hash(state), provider, verifier)
    params = {
        "client_id": config["client_id"], "redirect_uri": config["callback"], "response_type": "code",
        "scope": config["scope"], "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
    }
    if provider == "google":
        params["access_type"] = "online"
    return RedirectResponse(f"{config['authorize']}?{urllib.parse.urlencode(params)}", status_code=302)


async def _oauth_identity(provider: str, config: dict[str, str], code: str, verifier: str) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
        token_response = await client.post(
            config["token"],
            data={
                "grant_type": "authorization_code", "code": code, "redirect_uri": config["callback"],
                "client_id": config["client_id"], "client_secret": config["client_secret"],
                "code_verifier": verifier,
            },
            headers={"Accept": "application/json"},
        )
        _check_oauth_response(provider, "token exchange", token_response)
        token_data = token_response.json()
        access_token = str(token_data.get("access_token", ""))
        if not access_token:
            raise ValueError("Provider did not return an access token.")
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        if provider == "google":
            profile_response = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers=headers)
            _check_oauth_response(provider, "profile lookup", profile_response)
            profile = profile_response.json()
            if not profile.get("email_verified"):
                raise ValueError("The provider email address has not been verified.")
            return str(profile["email"]).lower(), str(profile.get("name") or "")
        if provider == "microsoft":
            profile_response = await client.get(
                "https://graph.microsoft.com/v1.0/me?$select=displayName,mail,userPrincipalName", headers=headers
            )
            _check_oauth_response(provider, "profile lookup", profile_response)
            profile = profile_response.json()
            return str(profile.get("mail") or profile["userPrincipalName"]).lower(), str(profile.get("displayName") or "")
        profile_response = await client.get("https://api.github.com/user", headers=headers)
        _check_oauth_response(provider, "profile lookup", profile_response)
        profile = profile_response.json()
        email_response = await client.get("https://api.github.com/user/emails", headers=headers)
        _check_oauth_response(provider, "email lookup", email_response)
        emails = email_response.json()
        primary = next((item for item in emails if item.get("primary") and item.get("verified")), None)
        if not primary:
            raise ValueError("Verify a primary email address with GitHub before signing in.")
        return str(primary["email"]).lower(), str(profile.get("name") or profile.get("login") or "")


def _check_oauth_response(provider: str, stage: str, response: httpx.Response) -> None:
    if response.is_error:
        error_code = "unknown"
        try:
            payload = response.json()
            candidate = payload.get("error") or payload.get("code") if isinstance(payload, dict) else None
            if isinstance(candidate, dict):
                candidate = candidate.get("code")
            if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,64}", candidate):
                error_code = candidate
        except ValueError:
            pass
        logger.warning(
            "OAuth %s %s failed with HTTP %d (provider error %s)",
            provider,
            stage,
            response.status_code,
            error_code,
        )
    response.raise_for_status()


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str, request: Request, code: str | None = None, state: str | None = None, error: str | None = None
) -> RedirectResponse:
    frontend = (
        os.getenv("MICROSOFT_FRONTEND_URL", "http://127.0.0.1:5173")
        if provider == "microsoft"
        else os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")
    ).rstrip("/")
    if error or not code or not state:
        return RedirectResponse(f"{frontend}/?auth_error=provider_cancelled", status_code=303)
    config = _provider_config(provider)
    store = _store(request)
    verifier = await asyncio.to_thread(store.consume_oauth_state, store.token_hash(state), provider)
    if not verifier:
        return RedirectResponse(f"{frontend}/?auth_error=state_expired", status_code=303)
    try:
        email, full_name = await _oauth_identity(provider, config, code, verifier)
        if not EMAIL_PATTERN.fullmatch(email):
            raise ValueError("The provider did not return a valid email address.")
        user = await asyncio.to_thread(store.find_or_create_oauth_user, email, full_name)
        response = RedirectResponse(f"{frontend}/auth/callback", status_code=303)
        _set_session(response, request, user, provider=provider)
        return response
    except httpx.HTTPError as failure:
        logger.warning("OAuth %s sign-in failed during provider communication (%s)", provider, type(failure).__name__)
        return RedirectResponse(f"{frontend}/?auth_error=provider_failed", status_code=303)
    except (KeyError, ValueError) as failure:
        logger.warning("OAuth %s sign-in failed profile validation (%s)", provider, type(failure).__name__)
        return RedirectResponse(f"{frontend}/?auth_error=provider_failed", status_code=303)
