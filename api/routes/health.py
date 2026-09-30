from __future__ import annotations

from fastapi import APIRouter, Request

from api.schemas import HealthResponse


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status="online",
        service="SHAH INDUSTRIES CAD API",
        route_count=len(request.app.openapi().get("paths", {})),
    )
