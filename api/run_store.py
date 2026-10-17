from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from agent.contracts import RunState


class RunStore:
    """Concurrency-safe local API index; graph checkpoints live in Postgres."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.path = Path(database_path or os.getenv("PLACEMENTGAP_RUN_DB") or "./data/runs.sqlite3")
        self.root = Path(os.getenv("PLACEMENTGAP_RUN_FILES", "./data/runs"))
        self._lock = asyncio.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, status TEXT NOT NULL, state_json TEXT NOT NULL, idempotency_key TEXT UNIQUE, request_id TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS run_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_run_events_run_seq ON run_events(run_id,seq)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _run_dir(self, run_id: str) -> Path:
        target = (self.root / run_id).resolve()
        if self.root.resolve() not in target.parents:
            raise ValueError("Invalid run id")
        return target

    def _serialize(self, state: RunState) -> str:
        payload = state.model_dump(mode="python")
        payload["report_pdf"] = None
        return json.dumps(payload, ensure_ascii=False)

    async def create(self, state: RunState, idempotency_key: str) -> tuple[RunState, bool]:
        async with self._lock:
            return await asyncio.to_thread(self._create, state, idempotency_key)

    def _create(self, state: RunState, idempotency_key: str) -> tuple[RunState, bool]:
        with self._connect() as connection:
            row = connection.execute("SELECT state_json FROM runs WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if row:
                return self._load_row(row), True
            connection.execute(
                "INSERT INTO runs(run_id,status,state_json,idempotency_key,request_id) VALUES(?,?,?,?,?)",
                (state.run_id, state.status, self._serialize(state), idempotency_key, state.request_id),
            )
            connection.commit()
        self._write_report_files(state)
        return state, False

    def _load_row(self, row: sqlite3.Row) -> RunState:
        state = RunState.model_validate_json(row["state_json"])
        pdf_path = self._run_dir(state.run_id) / "report.pdf"
        if pdf_path.exists():
            state.report_pdf = pdf_path.read_bytes()
        return state

    def _write_report_files(self, state: RunState) -> None:
        run_dir = self._run_dir(state.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        if state.report_pdf:
            (run_dir / "report.pdf").write_bytes(state.report_pdf)
        if state.report_markdown is not None:
            (run_dir / "report.md").write_text(state.report_markdown, encoding="utf-8")
        if state.report_json is not None:
            (run_dir / "report.json").write_text(json.dumps(state.report_json, indent=2, ensure_ascii=False), encoding="utf-8")

    async def update(self, state: RunState) -> None:
        async with self._lock:
            await asyncio.to_thread(self._update, state)

    def _update(self, state: RunState) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE runs SET status=?,state_json=?,updated_at=CURRENT_TIMESTAMP WHERE run_id=?",
                (state.status, self._serialize(state), state.run_id),
            )
            connection.commit()
        self._write_report_files(state)

    async def get(self, run_id: str) -> RunState | None:
        async with self._lock:
            return await asyncio.to_thread(self._get, run_id)

    def _get(self, run_id: str) -> RunState | None:
        with self._connect() as connection:
            row = connection.execute("SELECT state_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return self._load_row(row) if row else None

    async def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> int:
        async with self._lock:
            return await asyncio.to_thread(self._append_event, run_id, event_type, payload)

    def _append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO run_events(run_id,event_type,payload_json) VALUES(?,?,?)",
                (run_id, event_type, json.dumps(payload, ensure_ascii=False, default=str)),
            )
            connection.commit()
            if cursor.lastrowid is None:
                raise RuntimeError("The run event insert did not return a sequence number")
            return cursor.lastrowid

    async def events_after(self, run_id: str, sequence: int) -> list[dict[str, Any]]:
        async with self._lock:
            return await asyncio.to_thread(self._events_after, run_id, sequence)

    def _events_after(self, run_id: str, sequence: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT seq,event_type,payload_json,created_at FROM run_events WHERE run_id=? AND seq>? ORDER BY seq",
                (run_id, sequence),
            ).fetchall()
        return [
            {"id": row["seq"], "type": row["event_type"], "data": json.loads(row["payload_json"]), "created_at": row["created_at"]}
            for row in rows
        ]

    async def list_runs(self, limit: int = 50) -> list[RunState]:
        async with self._lock:
            return await asyncio.to_thread(self._list_runs, limit)

    def _list_runs(self, limit: int) -> list[RunState]:
        with self._connect() as connection:
            rows = connection.execute("SELECT state_json FROM runs ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._load_row(row) for row in rows]
