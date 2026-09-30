from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import assemblies, capabilities, editing, engineering, evaluation, exports, generation, health, learning, parametrics, preview, projects, revisions


def create_app() -> FastAPI:
    app = FastAPI(
        title="SHAH INDUSTRIES CAD API",
        version="0.7.0",
        description="Safe API layer for prompt-to-STEP generation, revisions, exports, learning, and capabilities.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
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
    return app


app = create_app()
