from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any


class AuthStore:
    """Small SQLite-backed account and one-time-code store for the local API."""

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.getenv("PLACEMENTGAP_AUTH_DB") or "./data/auth.sqlite3")

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    full_name TEXT NOT NULL,
                    phone TEXT UNIQUE,
                    password_hash TEXT,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
                CREATE TABLE IF NOT EXISTS otp_challenges (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL COLLATE NOCASE,
                    purpose TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    consumed INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS otp_email_idx ON otp_challenges(email, purpose, created_at);
                CREATE TABLE IF NOT EXISTS oauth_states (
                    state_hash TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    verifier TEXT NOT NULL,
                    expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS user_workspaces (
                    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    payload_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS login_attempts (
                    email TEXT NOT NULL COLLATE NOCASE,
                    client_ip TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    succeeded INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS login_attempts_lookup_idx ON login_attempts(email, client_ip, created_at);
                """
            )

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def clean_expired(self) -> None:
        now = time.time()
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
            db.execute("DELETE FROM otp_challenges WHERE expires_at < ? OR consumed = 1", (now - 86400,))
            db.execute("DELETE FROM oauth_states WHERE expires_at < ?", (now,))
            db.execute("DELETE FROM login_attempts WHERE created_at < ?", (now - 86400,))

    def login_rate_limited(self, email: str, client_ip: str) -> bool:
        with self.connect() as db:
            row = db.execute(
                """SELECT COUNT(*) AS count FROM login_attempts
                   WHERE email = ? COLLATE NOCASE AND client_ip = ? AND succeeded = 0 AND created_at > ?""",
                (email, client_ip, time.time() - 900),
            ).fetchone()
        return bool(row and int(row["count"]) >= 10)

    def record_login_attempt(self, email: str, client_ip: str, succeeded: bool) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO login_attempts(email,client_ip,created_at,succeeded) VALUES(?,?,?,?)",
                (email, client_ip, time.time(), int(succeeded)),
            )

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
        return dict(row) if row else None

    def get_user_by_session(self, token: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                """SELECT users.* FROM sessions JOIN users ON users.id = sessions.user_id
                   WHERE sessions.token_hash = ? AND sessions.expires_at > ?""",
                (self.token_hash(token), time.time()),
            ).fetchone()
        return dict(row) if row else None

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(36)
        now = time.time()
        with self.connect() as db:
            db.execute(
                "INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                (self.token_hash(token), user_id, now + 30 * 86400, now),
            )
        return token

    def revoke_session(self, token: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (self.token_hash(token),))

    def create_user(
        self, *, email: str, full_name: str, phone: str | None, password_hash: str | None
    ) -> dict[str, Any]:
        user_id = secrets.token_urlsafe(18)
        with self.connect() as db:
            db.execute(
                "INSERT INTO users(id,email,full_name,phone,password_hash,created_at) VALUES(?,?,?,?,?,?)",
                (user_id, email, full_name, phone, password_hash, time.time()),
            )
            row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row)

    def update_password(self, email: str, password_hash: str) -> bool:
        with self.connect() as db:
            result = db.execute(
                "UPDATE users SET password_hash = ? WHERE email = ? COLLATE NOCASE",
                (password_hash, email),
            )
            return result.rowcount == 1

    def create_challenge(
        self,
        *,
        challenge_id: str,
        email: str,
        purpose: str,
        code_hash: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        now = time.time()
        with self.connect() as db:
            latest = db.execute(
                "SELECT created_at FROM otp_challenges WHERE email = ? AND purpose = ? AND consumed = 0 ORDER BY created_at DESC LIMIT 1",
                (email, purpose),
            ).fetchone()
            if latest and now - float(latest["created_at"]) < 30:
                raise ValueError("Please wait 30 seconds before requesting another code.")
            db.execute(
                "UPDATE otp_challenges SET consumed = 1 WHERE email = ? AND purpose = ? AND consumed = 0",
                (email, purpose),
            )
            db.execute(
                """INSERT INTO otp_challenges
                   (id,email,purpose,code_hash,payload_json,created_at,expires_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (challenge_id, email, purpose, code_hash, json.dumps(payload or {}), now, now + 600),
            )

    def verify_challenge(self, challenge_id: str, code_hash: str, purpose: str) -> dict[str, Any] | None:
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM otp_challenges WHERE id = ?", (challenge_id,)).fetchone()
            if not row or row["purpose"] != purpose or row["consumed"] or row["expires_at"] <= now:
                db.rollback()
                return None
            attempts = int(row["attempts"]) + 1
            valid = secrets.compare_digest(str(row["code_hash"]), code_hash)
            db.execute(
                "UPDATE otp_challenges SET attempts = ?, consumed = ? WHERE id = ?",
                (attempts, int(valid or attempts >= 5), challenge_id),
            )
            if not valid or attempts > 5:
                db.commit()
                return None
            payload = json.loads(str(row["payload_json"]))
            result = {"id": challenge_id, "email": str(row["email"]), "payload": payload}
            db.commit()
            return result

    def consume_challenge(self, challenge_id: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE otp_challenges SET consumed = 1 WHERE id = ?", (challenge_id,))

    def save_oauth_state(self, state_hash: str, provider: str, verifier: str) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO oauth_states(state_hash,provider,verifier,expires_at) VALUES(?,?,?,?)",
                (state_hash, provider, verifier, time.time() + 600),
            )

    def consume_oauth_state(self, state_hash: str, provider: str) -> str | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT verifier,expires_at FROM oauth_states WHERE state_hash = ? AND provider = ?",
                (state_hash, provider),
            ).fetchone()
            db.execute("DELETE FROM oauth_states WHERE state_hash = ?", (state_hash,))
            db.commit()
        if not row or float(row["expires_at"]) <= time.time():
            return None
        return str(row["verifier"])

    def find_or_create_oauth_user(self, email: str, name: str) -> dict[str, Any]:
        existing = self.get_user_by_email(email)
        if existing:
            return existing
        return self.create_user(email=email, full_name=name or email.split("@")[0], phone=None, password_hash=None)

    def get_workspace(self, user_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload_json FROM user_workspaces WHERE user_id = ?", (user_id,)
            ).fetchone()
        return json.loads(str(row["payload_json"])) if row else None

    def save_workspace(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 400_000:
            raise ValueError("Workspace data exceeds the 400 KB limit.")
        with self.connect() as db:
            db.execute(
                """INSERT INTO user_workspaces(user_id,payload_json,updated_at) VALUES(?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET payload_json=excluded.payload_json,
                   updated_at=excluded.updated_at""",
                (user_id, encoded, time.time()),
            )
        return payload
