from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from engineering.analyzer import analyze_part
from engineering.materials import UnknownMaterialError, get_material, list_materials
from engineering.models import EngineeringReport, ManufacturingProcess, MaterialSpec
from projects.serialization import model_from_json
from projects.store import ProjectStore

from api.dependencies import get_project_store
from api.schemas import MaterialAssignmentRequest


router = APIRouter(prefix="/api", tags=["engineering"])


@router.get("/materials", response_model=list[MaterialSpec])
def materials() -> list[MaterialSpec]:
    return list_materials()


@router.get("/projects/{project_id}/engineering", response_model=EngineeringReport)
def project_engineering_report(
    project_id: str,
    revision: int | None = None,
    material: str | None = None,
    process: ManufacturingProcess = ManufacturingProcess.UNKNOWN,
    display_units: str = "mm",
    store: ProjectStore = Depends(get_project_store),
) -> EngineeringReport:
    revision_record = (
        store.current_revision(project_id)
        if revision is None
        else store.get_revision(project_id, revision)
    )
    if revision_record is None:
        raise HTTPException(status_code=404, detail="Project revision not found.")
    material_id = material if material is not None else store.get_material_assignment(project_id)
    try:
        model = model_from_json(revision_record.model_type, revision_record.structured_spec_json)
        return analyze_part(
            model,
            project_id=project_id,
            revision_number=revision_record.revision_number,
            material_id=material_id,
            manufacturing_process=process,
            display_units=display_units,
        )
    except UnknownMaterialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/material")
def set_project_material(
    project_id: str,
    request: MaterialAssignmentRequest,
    store: ProjectStore = Depends(get_project_store),
) -> dict[str, str | None]:
    try:
        if request.material_id:
            get_material(request.material_id)
        store.set_material_assignment(project_id, request.material_id)
        return {"project_id": project_id, "material_id": request.material_id}
    except UnknownMaterialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
