from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import assemblies, capabilities, editing, engineering, evaluation, exports, generation, health, learning, parametrics, preview, projects, revisions, version
from api.static_frontend import dist_is_built, mount_frontend
from shah_version import APP_VERSION


def create_app(static_dir: Path | None = None) -> FastAPI:
    """Build the API. Pass `static_dir` to also serve a built frontend.

    Without `static_dir` this is API-only, which is what development mode (Vite
    proxying /api) and the test suite use.
    """
    app = FastAPI(
        title="SHAH INDUSTRIES CAD API",
        version=APP_VERSION,
        description="Safe API layer for prompt-to-STEP generation, revisions, exports, learning, and capabilities.",
    )
    app.add_middleware(
        CORSMiddleware,
        # Only the Vite dev origins. Production mode is same-origin and does not
        # rely on CORS at all.
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(version.router)
    app.include_router(generation.router)
    app.include_router(assemblies.router)
    app.include_router(projects.router)
    app.include_router(editing.router)
    app.include_router(revisions.router)
    app.include_router(exports.router)
    app.include_router(engineering.router)
    app.include_router(evaluation.router)
    app.include_router(learning.router)
    app.include_router(capabilities.router)
    app.include_router(parametrics.router)
    app.include_router(preview.router)

    # Registered last so the SPA catch-all cannot shadow an API route.
    if static_dir is not None and dist_is_built(static_dir):
        mount_frontend(app, static_dir)
    return app


def _static_dir_from_env() -> Path | None:
    """Production mode sets SHAH_SERVE_FRONTEND so `uvicorn api.server:app` serves it."""
    raw = os.getenv("SHAH_SERVE_FRONTEND")
    if not raw:
        return None
    if raw.strip().lower() in {"1", "true", "yes", "on"}:
        return Path(__file__).resolve().parents[1] / "web" / "dist"
    return Path(raw)


app = create_app(_static_dir_from_env())
