from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.dependencies import get_assembly_store, get_export_store, get_project_store
from assemblies.store import AssemblyStore
from exports.manager import ExportError, run_export
from exports.models import ExportFormat, ExportRequest, ExportSourceType
from exports.store import ExportStore
from projects.store import ProjectStore


router = APIRouter(prefix="/api", tags=["exports"])


@router.post("/exports")
def create_export(
    request: ExportRequest,
    project_store: ProjectStore = Depends(get_project_store),
    assembly_store: AssemblyStore = Depends(get_assembly_store),
    export_store: ExportStore = Depends(get_export_store),
) -> dict[str, object]:
    try:
        return run_export(request, project_store=project_store, assembly_store=assembly_store, export_store=export_store).model_dump(mode="json")
    except ExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/exports/{export_id}")
def get_export(export_id: str, export_store: ExportStore = Depends(get_export_store)) -> dict[str, object]:
    record = export_store.get(export_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Export not found.")
    return record.model_dump(mode="json")


@router.get("/exports/{export_id}/download")
def download_export(export_id: str, export_store: ExportStore = Depends(get_export_store)) -> FileResponse:
    record = export_store.get(export_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Export not found.")
    path = Path(record.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export file not found.")
    return FileResponse(path, media_type=_media_type(record.format), filename=record.filename)


@router.get("/projects/{project_id}/exports")
def project_exports(project_id: str, export_store: ExportStore = Depends(get_export_store)) -> list[dict[str, object]]:
    return [item.model_dump(mode="json") for item in export_store.list_for_source(ExportSourceType.PROJECT_REVISION, project_id)]


@router.get("/assemblies/{assembly_id}/exports")
def assembly_exports(assembly_id: str, export_store: ExportStore = Depends(get_export_store)) -> list[dict[str, object]]:
    return [item.model_dump(mode="json") for item in export_store.list_for_source(ExportSourceType.ASSEMBLY_REVISION, assembly_id)]


@router.post("/projects/{project_id}/revisions/{revision}/export")
def export_project_revision(
    project_id: str,
    revision: int,
    request: ExportRequest,
    project_store: ProjectStore = Depends(get_project_store),
    assembly_store: AssemblyStore = Depends(get_assembly_store),
    export_store: ExportStore = Depends(get_export_store),
) -> dict[str, object]:
    request = request.model_copy(update={"source_type": ExportSourceType.PROJECT_REVISION, "source_id": project_id, "revision": revision})
    return create_export(request, project_store, assembly_store, export_store)


@router.get("/projects/{project_id}/download/step")
def download_step(
    project_id: str,
    revision: int | None = None,
    project_store: ProjectStore = Depends(get_project_store),
    assembly_store: AssemblyStore = Depends(get_assembly_store),
    export_store: ExportStore = Depends(get_export_store),
) -> FileResponse:
    request = ExportRequest(source_type=ExportSourceType.PROJECT_REVISION, source_id=project_id, revision=revision, formats=[ExportFormat.STEP])
    try:
        batch = run_export(request, project_store=project_store, assembly_store=assembly_store, export_store=export_store)
    except ExportError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = next(item for item in batch.results if item.format == ExportFormat.STEP)
    return FileResponse(result.path, media_type="model/step", filename=result.filename)


@router.get("/projects/{project_id}/download/stl")
def download_stl(
    project_id: str,
    revision: int | None = None,
    project_store: ProjectStore = Depends(get_project_store),
    assembly_store: AssemblyStore = Depends(get_assembly_store),
    export_store: ExportStore = Depends(get_export_store),
) -> FileResponse:
    request = ExportRequest(source_type=ExportSourceType.PROJECT_REVISION, source_id=project_id, revision=revision, formats=[ExportFormat.STL])
    try:
        batch = run_export(request, project_store=project_store, assembly_store=assembly_store, export_store=export_store)
    except ExportError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = next(item for item in batch.results if item.format == ExportFormat.STL)
    return FileResponse(result.path, media_type="model/stl", filename=result.filename)


def _media_type(format_name: ExportFormat) -> str:
    return {
        ExportFormat.STEP: "model/step",
        ExportFormat.STL: "model/stl",
        ExportFormat.DXF: "application/dxf",
        ExportFormat.MANIFEST: "application/json",
        ExportFormat.ZIP: "application/zip",
    }.get(format_name, "application/octet-stream")
