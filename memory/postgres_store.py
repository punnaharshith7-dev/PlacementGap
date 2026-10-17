from __future__ import annotations

import json
import os
from typing import Any

from memory.embeddings import embed_text


def _connect() -> Any:
    import psycopg
    from pgvector.psycopg import register_vector

    connection = psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5)
    register_vector(connection)
    return connection


def init_schema() -> None:
    with _connect() as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS student_profiles (student_id TEXT PRIMARY KEY, payload JSONB NOT NULL, embedding vector(192) NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS semantic_jd_cache (content_hash TEXT PRIMARY KEY, role TEXT NOT NULL, payload JSONB NOT NULL, source_text TEXT NOT NULL, embedding vector(192) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS semantic_jd_role_idx ON semantic_jd_cache(role, created_at)")


def get_profile(student_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("SELECT payload FROM student_profiles WHERE student_id=%s", (student_id,)).fetchone()
    if not row:
        return None
    return row[0] if isinstance(row[0], dict) else json.loads(row[0])


def save_profile(student_id: str, payload: dict[str, Any], raw_text: str) -> None:
    from pgvector import Vector

    with _connect() as connection:
        connection.execute(
            "INSERT INTO student_profiles(student_id,payload,embedding,updated_at) VALUES(%s,%s::jsonb,%s,now()) "
            "ON CONFLICT(student_id) DO UPDATE SET payload=excluded.payload,embedding=excluded.embedding,updated_at=now()",
            (student_id, json.dumps(payload), Vector(embed_text(raw_text))),
        )


def get_jd(content_digest: str, role: str, query_text: str) -> tuple[dict[str, Any] | None, bool]:
    from pgvector import Vector

    with _connect() as connection:
        exact = connection.execute(
            "SELECT payload FROM semantic_jd_cache WHERE content_hash=%s AND created_at >= now() - interval '14 days'",
            (content_digest,),
        ).fetchone()
        if exact:
            payload = exact[0] if isinstance(exact[0], dict) else json.loads(exact[0])
            return payload, True
        query_vector = Vector(embed_text(query_text))
        nearest = connection.execute(
            "SELECT payload, 1 - (embedding <=> %s) AS similarity FROM semantic_jd_cache "
            "WHERE role=%s AND created_at >= now() - interval '14 days' ORDER BY embedding <=> %s LIMIT 1",
            (query_vector, role.casefold(), query_vector),
        ).fetchone()
    if nearest and float(nearest[1]) >= 0.94:
        payload = nearest[0] if isinstance(nearest[0], dict) else json.loads(nearest[0])
        return payload, True
    return None, False


def save_jd(content_digest: str, role: str, payload: dict[str, Any], text: str) -> None:
    from pgvector import Vector

    with _connect() as connection:
        connection.execute(
            "INSERT INTO semantic_jd_cache(content_hash,role,payload,source_text,embedding) VALUES(%s,%s,%s::jsonb,%s,%s) "
            "ON CONFLICT(content_hash) DO UPDATE SET role=excluded.role,payload=excluded.payload,source_text=excluded.source_text,embedding=excluded.embedding,created_at=now()",
            (content_digest, role.casefold(), json.dumps(payload), text, Vector(embed_text(text))),
        )
