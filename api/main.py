from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import FileResponse, Response

from agent.graph import PostgresCheckpointRuntime, create_graph
from agent.observability import configure_telemetry
from api.auth_routes import _auth_secret
from api.auth_routes import router as auth_router
from api.auth_store import AuthStore
from api.routes import router
from api.run_store import RunStore
from api.workspace_routes import router as workspace_router

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.run_store = RunStore()
    app.state.auth_store = AuthStore()
    await asyncio.to_thread(app.state.auth_store.initialize)
    await asyncio.to_thread(app.state.auth_store.clean_expired)
    app.state.auth_secret = _auth_secret()
    app.state.tasks = {}
    app.state.graph_runtime = None
    app.state.postgres_ready = False
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            from memory.postgres_store import init_schema

            await asyncio.to_thread(init_schema)
            runtime = PostgresCheckpointRuntime(database_url)
            await runtime.start()
            app.state.graph_runtime = runtime
            app.state.graph = runtime.graph
            app.state.postgres_ready = True
            logger.info("Postgres checkpoint and pgvector stores are ready")
        except Exception:
            logger.exception("Postgres initialization failed; using in-memory graph checkpoints")
            app.state.graph = create_graph()
    else:
        app.state.graph = create_graph()
    yield
    for task in app.state.tasks.values():
        if not task.done():
            task.cancel()
    if app.state.tasks:
        await asyncio.gather(*app.state.tasks.values(), return_exceptions=True)
    if app.state.graph_runtime:
        await app.state.graph_runtime.stop()


app = FastAPI(
    title="PlacementGap API",
    version="1.0.0",
    description="Evidence-grounded student-to-role gap analysis and learning plans.",
    lifespan=lifespan,
)
configure_telemetry(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
async def health() -> dict[str, object]:
    return {"status": "ok", "service": "placementgap-api", "postgres": bool(getattr(app.state, "postgres_ready", False))}


app.include_router(router)
app.include_router(auth_router)
app.include_router(workspace_router)


web_dist_value = os.getenv("PLACEMENTGAP_WEB_DIST")
if web_dist_value:
    web_dist = Path(web_dist_value).resolve()
    index_file = web_dist / "index.html"
    if index_file.is_file():
        @app.get("/{asset_path:path}", include_in_schema=False)
        async def serve_web_app(asset_path: str) -> FileResponse:
            requested_file = (web_dist / asset_path).resolve()
            if not requested_file.is_relative_to(web_dist):
                raise HTTPException(status_code=404, detail="Not found")
            if requested_file.is_file():
                return FileResponse(requested_file)

            # Keep unknown API URLs as 404s instead of returning the SPA shell.
            first_segment = asset_path.partition("/")[0]
            api_segments = {
                "auth",
                "docs",
                "evals",
                "health",
                "openapi.json",
                "redoc",
                "runs",
                "workspace",
            }
            if first_segment in api_segments and asset_path.rstrip("/") != "auth/callback":
                raise HTTPException(status_code=404, detail="Not found")
            if Path(asset_path).suffix:
                raise HTTPException(status_code=404, detail="Not found")
            return FileResponse(index_file)
