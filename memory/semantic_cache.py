from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from memory.embeddings import cosine, embed_text

TTL_DAYS = 14
SIMILARITY_THRESHOLD = 0.94
logger = logging.getLogger(__name__)


def _connect() -> sqlite3.Connection:
    path = Path(os.getenv("PLACEMENTGAP_SQLITE_PATH", "./data/placementgap.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS jd_cache (content_hash TEXT PRIMARY KEY, role TEXT NOT NULL, payload TEXT NOT NULL, embedding TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    connection.commit()
    return connection


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).casefold().encode("utf-8")).hexdigest()


def _get(content_digest: str, role: str, query_text: str = "") -> tuple[dict[str, Any] | None, bool]:
    if os.getenv("PLACEMENTGAP_ABLATION") == "no_memory":
        return None, False
    if os.getenv("DATABASE_URL"):
        try:
            from memory.postgres_store import get_jd

            return get_jd(content_digest, role, query_text)
        except Exception:  # noqa: BLE001 - SQLite is the documented fallback when Postgres is unavailable.
            logger.warning("Postgres JD cache lookup failed; using the local SQLite cache.")
    with _connect() as connection:
        rows = connection.execute("SELECT payload, embedding, created_at, content_hash FROM jd_cache WHERE role=?", (role.casefold(),)).fetchall()
    cutoff = datetime.now(UTC) - timedelta(days=TTL_DAYS)
    nearest: tuple[float, dict[str, Any], bool] | None = None
    for payload_json, embedding_json, created_at, row_hash in rows:
        try:
            created = datetime.fromisoformat(created_at)
        except ValueError:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if created < cutoff:
            continue
        payload = json.loads(payload_json)
        if row_hash == content_digest:
            return payload, True
        similarity = cosine(embed_text(query_text), json.loads(embedding_json)) if query_text else 0.0
        if similarity >= SIMILARITY_THRESHOLD and (nearest is None or similarity > nearest[0]):
            nearest = (similarity, payload, True)
    return (nearest[1], nearest[2]) if nearest else (None, False)


def _put(content_digest: str, role: str, payload: dict[str, Any], text: str) -> None:
    if os.getenv("PLACEMENTGAP_ABLATION") == "no_memory":
        return
    if os.getenv("DATABASE_URL"):
        try:
            from memory.postgres_store import save_jd

            save_jd(content_digest, role, payload, text)
            return
        except Exception:  # noqa: BLE001 - SQLite is the documented fallback when Postgres is unavailable.
            logger.warning("Postgres JD cache write failed; using the local SQLite cache.")
    with _connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO jd_cache(content_hash,role,payload,embedding,created_at) VALUES(?,?,?,?,?)",
            (content_digest, role.casefold(), json.dumps(payload), json.dumps(embed_text(text)), datetime.now(UTC).isoformat()),
        )
        connection.commit()


async def get_cached_jd(content_digest: str, role: str, query_text: str = "") -> tuple[dict[str, Any] | None, bool]:
    return await asyncio.to_thread(_get, content_digest, role, query_text)


async def cache_jd(content_digest: str, role: str, payload: dict[str, Any], text: str) -> None:
    await asyncio.to_thread(_put, content_digest, role, payload, text)
