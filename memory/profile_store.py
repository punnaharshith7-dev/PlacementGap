from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from pathlib import Path

from agent.contracts import StudentProfile

logger = logging.getLogger(__name__)


def _database_path() -> Path:
    return Path(os.getenv("PLACEMENTGAP_SQLITE_PATH", "./data/placementgap.sqlite3"))


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS profiles (student_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    connection.commit()
    return connection


def _get(student_id: str) -> StudentProfile | None:
    if os.getenv("PLACEMENTGAP_ABLATION") == "no_memory":
        return None
    if os.getenv("DATABASE_URL"):
        try:
            from memory.postgres_store import get_profile as get_postgres_profile

            payload = get_postgres_profile(student_id)
            return StudentProfile.model_validate(payload) if payload else None
        except Exception:  # noqa: BLE001 - SQLite is the documented fallback when Postgres is unavailable.
            logger.warning("Postgres profile lookup failed; using the local SQLite profile store.")
    with _connect() as connection:
        row = connection.execute("SELECT payload FROM profiles WHERE student_id=?", (student_id,)).fetchone()
    return StudentProfile.model_validate_json(row[0]) if row else None


def _save(profile: StudentProfile) -> None:
    if os.getenv("PLACEMENTGAP_ABLATION") == "no_memory":
        return
    if os.getenv("DATABASE_URL"):
        try:
            from memory.postgres_store import save_profile as save_postgres_profile

            save_postgres_profile(
                profile.student_id,
                profile.model_dump(mode="json"),
                profile.raw_text,
            )
            return
        except Exception:  # noqa: BLE001 - SQLite is the documented fallback when Postgres is unavailable.
            logger.warning("Postgres profile write failed; using the local SQLite profile store.")
    with _connect() as connection:
        connection.execute(
            "INSERT INTO profiles(student_id,payload,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) "
            "ON CONFLICT(student_id) DO UPDATE SET payload=excluded.payload, updated_at=CURRENT_TIMESTAMP",
            (profile.student_id, profile.model_dump_json()),
        )
        connection.commit()


async def get_profile(student_id: str) -> StudentProfile | None:
    return await asyncio.to_thread(_get, student_id)


async def save_profile(profile: StudentProfile) -> None:
    await asyncio.to_thread(_save, profile)
