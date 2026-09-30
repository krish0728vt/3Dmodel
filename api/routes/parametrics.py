from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import ParametricValidateRequest
from api.utils import parse_design_spec
from parametrics.resolver import ParametricResolutionError, resolve_design_intent


router = APIRouter(prefix="/api/parametrics", tags=["parametrics"])


@router.post("/validate")
def validate_parametrics(request: ParametricValidateRequest) -> dict[str, object]:
    model = parse_design_spec(request.spec)
    try:
        resolved = resolve_design_intent(model)
    except ParametricResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "valid": True,
        "parameters": [parameter.model_dump(mode="json") for parameter in resolved.parameters],
        "relationships": [relationship.model_dump(mode="json") for relationship in resolved.relationships],
        "resolved_parameters": resolved.resolved_parameters,
        "derived_values": resolved.derived_values,
        "resolved_model": resolved.resolved_model.model_dump(mode="json"),
        "diagnostics": resolved.diagnostics,
    }
