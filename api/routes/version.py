from __future__ import annotations

import os
import sys

from fastapi import APIRouter

from api.schemas import VersionResponse
from shah_version import APP_VERSION, SCHEMA_VERSION, build_commit


router = APIRouter(prefix="/api", tags=["version"])


@router.get("/version", response_model=VersionResponse)
def version() -> VersionResponse:
    """Build and capability identity for the About panel.

    Deliberately reports only presence of an API key, never its value, and no
    other environment contents.
    """
    return VersionResponse(
        app_version=APP_VERSION,
        schema_version=SCHEMA_VERSION,
        build=build_commit(),
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        cad_engine=_cad_engine(),
        ai_configured=bool(os.getenv("OPENAI_API_KEY")),
    )


def _cad_engine() -> str:
    try:
        import importlib.metadata

        return f"CadQuery {importlib.metadata.version('cadquery')}"
    except Exception:  # noqa: BLE001 - version reporting must never break the route
        return "CadQuery"
