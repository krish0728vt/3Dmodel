from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_capability_registry, get_learning_store
from api.schemas import CapabilityApproveRequest, CapabilityDiscoverRequest, CapabilityInvokeApiRequest
from capabilities.invocation import CapabilityInvocationError, invoke_capability
from capabilities.registry import CapabilityRegistry
from learning.store import LearningStore


router = APIRouter(prefix="/api", tags=["capabilities"])


@router.get("/capabilities")
def capabilities(registry: CapabilityRegistry = Depends(get_capability_registry)) -> list[dict[str, object]]:
    return [capability.model_dump(mode="json") for capability in registry.list()]


@router.get("/capabilities/sources")
def capability_sources(registry: CapabilityRegistry = Depends(get_capability_registry)) -> list[dict[str, object]]:
    return [source.model_dump(mode="json") for source in registry.list_sources()]


@router.post("/capabilities/discover")
def discover_capabilities(
    request: CapabilityDiscoverRequest,
    registry: CapabilityRegistry = Depends(get_capability_registry),
) -> list[dict[str, object]]:
    try:
        return [capability.model_dump(mode="json") for capability in registry.discover(request.source_id)]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/capabilities/{capability_id:path}")
def inspect_capability(
    capability_id: str,
    registry: CapabilityRegistry = Depends(get_capability_registry),
) -> dict[str, object]:
    capability = registry.get(capability_id)
    if capability is None:
        raise HTTPException(status_code=404, detail="Capability not found.")
    return capability.model_dump(mode="json")


@router.post("/capabilities/{capability_id:path}/test")
def test_capability(
    capability_id: str,
    registry: CapabilityRegistry = Depends(get_capability_registry),
) -> dict[str, object]:
    try:
        return registry.run_self_test(capability_id).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/capabilities/{capability_id:path}/approve")
def approve_capability(
    capability_id: str,
    request: CapabilityApproveRequest,
    registry: CapabilityRegistry = Depends(get_capability_registry),
) -> dict[str, object]:
    try:
        return registry.approve(
            capability_id,
            approved_by=request.approved_by,
            notes=request.approval_notes,
        ).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/capabilities/{capability_id:path}/enable")
def enable_capability(
    capability_id: str,
    registry: CapabilityRegistry = Depends(get_capability_registry),
) -> dict[str, object]:
    try:
        return registry.enable(capability_id).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/capabilities/{capability_id:path}/disable")
def disable_capability(
    capability_id: str,
    registry: CapabilityRegistry = Depends(get_capability_registry),
) -> dict[str, object]:
    try:
        return registry.disable(capability_id).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/capabilities/{capability_id:path}/invoke")
def invoke_capability_route(
    capability_id: str,
    request: CapabilityInvokeApiRequest,
    registry: CapabilityRegistry = Depends(get_capability_registry),
    learning_store: LearningStore = Depends(get_learning_store),
) -> dict[str, object]:
    try:
        return invoke_capability(
            capability_id,
            request.arguments,
            registry=registry,
            learning_store=learning_store,
        ).model_dump(mode="json")
    except CapabilityInvocationError as exc:
        raise HTTPException(status_code=400, detail={"category": exc.category.value, "message": str(exc)}) from exc
