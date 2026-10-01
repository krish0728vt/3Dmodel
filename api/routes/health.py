from __future__ import annotations

from fastapi import APIRouter, Request

from api.schemas import HealthResponse
from shah_version import APP_VERSION


router = APIRouter(prefix="/api", tags=["system"])


def _cad_engine_ready() -> bool:
    """Whether CadQuery is importable.

    Checked against already-imported modules so a health poll stays cheap and
    never triggers an import or a geometry operation.
    """
    import sys

    return "cadquery" in sys.modules


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status="online",
        service="SHAH INDUSTRIES CAD API",
        route_count=len(request.app.openapi().get("paths", {})),
        version=APP_VERSION,
        cad_engine_ready=_cad_engine_ready(),
    )
