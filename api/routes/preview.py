from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.dependencies import get_project_store
from api.schemas import RevisionPreview
from cad.preview import ensure_final_stl, generate_revision_preview, preview_mesh_path
from projects.serialization import model_from_json
from projects.store import ProjectStore


router = APIRouter(prefix="/api/projects", tags=["preview"])


@router.get("/{project_id}/revisions/{revision}/preview", response_model=RevisionPreview)
def revision_preview(
    project_id: str,
    revision: int,
    store: ProjectStore = Depends(get_project_store),
) -> RevisionPreview:
    revision_record = store.get_revision(project_id, revision)
    if revision_record is None:
        raise HTTPException(status_code=404, detail="Project revision not found.")
    model = model_from_json(revision_record.model_type, revision_record.structured_spec_json)
    try:
        ensure_final_stl(model, project_id, revision_record.revision_number)
        return generate_revision_preview(model, project_id, revision_record.revision_number)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{project_id}/revisions/{revision}/preview/{operation_id}/mesh")
def revision_preview_mesh(
    project_id: str,
    revision: int,
    operation_id: str,
    store: ProjectStore = Depends(get_project_store),
) -> FileResponse:
    revision_record = store.get_revision(project_id, revision)
    if revision_record is None:
        raise HTTPException(status_code=404, detail="Project revision not found.")
    model = model_from_json(revision_record.model_type, revision_record.structured_spec_json)
    try:
        generate_revision_preview(model, project_id, revision_record.revision_number)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = preview_mesh_path(project_id, revision_record.revision_number, operation_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Preview mesh not found.")
    return FileResponse(path, media_type="model/stl", filename=path.name)
