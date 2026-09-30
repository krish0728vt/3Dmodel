from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from projects.manager import create_project_from_model
from projects.revisions import export_revision_stl
from projects.editor import EditApplicationError, apply_edit_to_project
from projects.models import SetDesignParameterEdit
from projects.serialization import model_from_json
from projects.store import ProjectStore
from parametrics.resolver import ParametricResolutionError, resolve_design_intent

from api.dependencies import get_project_store
from api.schemas import DeleteConfirmRequest, DuplicateRequest, ParameterUpdateRequest, ProjectCreateRequest, ProjectDetail, ProjectSummary, RenameRequest, RevisionSummary
from api.utils import parse_design_spec, project_detail, project_summary, revision_summary


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    search: str | None = None,
    status: str = Query("active", pattern="^(active|archived|all)$"),
    sort: str = Query("recently_updated", pattern="^(recently_updated|recently_opened|name|created)$"),
    store: ProjectStore = Depends(get_project_store),
) -> list[ProjectSummary]:
    try:
        projects = store.list_projects(search=search, status=status, sort=sort)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [project_summary(project, material=store.get_material_assignment(project.project_id)) for project in projects]


@router.post("", response_model=ProjectDetail)
def create_project(
    request: ProjectCreateRequest,
    store: ProjectStore = Depends(get_project_store),
) -> ProjectDetail:
    model = parse_design_spec(request.spec)
    project, revision = create_project_from_model(
        name=request.name,
        model=model,
        source_prompt=request.source_prompt,
        store=store,
    )
    export_revision_stl(project.project_id, revision.revision_number, store=store)
    project = store.get_project(project.project_id) or project
    return project_detail(project, revision)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, store: ProjectStore = Depends(get_project_store)) -> ProjectDetail:
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    store.mark_opened(project_id)
    project = store.get_project(project_id) or project
    return project_detail(project, store.current_revision(project_id))


@router.patch("/{project_id}", response_model=ProjectSummary)
def rename_project(project_id: str, request: RenameRequest, store: ProjectStore = Depends(get_project_store)) -> ProjectSummary:
    try:
        project = store.rename_project(project_id, request.name)
        return project_summary(project, material=store.get_material_assignment(project_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{project_id}/rename", response_model=ProjectSummary)
def rename_project_legacy(project_id: str, request: RenameRequest, store: ProjectStore = Depends(get_project_store)) -> ProjectSummary:
    return rename_project(project_id, request, store)


@router.post("/{project_id}/duplicate", response_model=ProjectDetail)
def duplicate_project(project_id: str, request: DuplicateRequest, store: ProjectStore = Depends(get_project_store)) -> ProjectDetail:
    try:
        project, revision = store.duplicate_project(project_id, revision_number=request.revision, name=request.name)
        export_revision_stl(project.project_id, revision.revision_number, store=store)
        project = store.get_project(project.project_id) or project
        return project_detail(project, revision)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{project_id}/archive", response_model=ProjectSummary)
def archive_project(project_id: str, store: ProjectStore = Depends(get_project_store)) -> ProjectSummary:
    try:
        project = store.archive_project(project_id)
        return project_summary(project, material=store.get_material_assignment(project_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{project_id}/unarchive", response_model=ProjectSummary)
def unarchive_project(project_id: str, store: ProjectStore = Depends(get_project_store)) -> ProjectSummary:
    try:
        project = store.unarchive_project(project_id)
        return project_summary(project, material=store.get_material_assignment(project_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{project_id}")
def delete_project(project_id: str, request: DeleteConfirmRequest, store: ProjectStore = Depends(get_project_store)) -> dict[str, object]:
    try:
        result = store.delete_project(project_id)
        return {"project_id": project_id, "deleted": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{project_id}/thumbnail")
def project_thumbnail(project_id: str, store: ProjectStore = Depends(get_project_store)) -> Response:
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    label = "PART" if project.model_type == "template" else "PLAN"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">
<rect width="320" height="180" fill="#101316"/>
<rect x="18" y="18" width="284" height="144" fill="#151b1f" stroke="#334047"/>
<path d="M74 114h122l38-42H112z" fill="#26343b" stroke="#8ae8fb"/>
<path d="M112 72v-25h122v25" fill="none" stroke="#4f646e"/>
<text x="28" y="44" fill="#8fa1a8" font-family="Arial" font-size="16">{label}</text>
<text x="28" y="150" fill="#e8f0f2" font-family="Arial" font-size="18">{_escape_svg(project.name[:28])}</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/{project_id}/history", response_model=list[RevisionSummary])
def project_history(project_id: str, store: ProjectStore = Depends(get_project_store)) -> list[RevisionSummary]:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return [revision_summary(revision) for revision in store.history(project_id)]


@router.get("/{project_id}/parameters")
def project_parameters(project_id: str, store: ProjectStore = Depends(get_project_store)) -> list[dict[str, object]]:
    model = _current_model(project_id, store)
    return [parameter.model_dump(mode="json") for parameter in getattr(model, "parameters", [])]


@router.get("/{project_id}/relationships")
def project_relationships(project_id: str, store: ProjectStore = Depends(get_project_store)) -> list[dict[str, object]]:
    model = _current_model(project_id, store)
    return [relationship.model_dump(mode="json") for relationship in getattr(model, "relationships", [])]


@router.get("/{project_id}/resolved-design")
def project_resolved_design(project_id: str, store: ProjectStore = Depends(get_project_store)) -> dict[str, object]:
    model = _current_model(project_id, store)
    try:
        resolved = resolve_design_intent(model)
    except ParametricResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "parameters": [parameter.model_dump(mode="json") for parameter in resolved.parameters],
        "relationships": [relationship.model_dump(mode="json") for relationship in resolved.relationships],
        "resolved_parameters": resolved.resolved_parameters,
        "derived_values": resolved.derived_values,
        "resolved_model": resolved.resolved_model.model_dump(mode="json"),
        "diagnostics": resolved.diagnostics,
    }


@router.post("/{project_id}/parameters/{parameter_id}")
def update_project_parameter(
    project_id: str,
    parameter_id: str,
    request: ParameterUpdateRequest,
    store: ProjectStore = Depends(get_project_store),
) -> dict[str, object]:
    if store.current_revision(project_id) is None:
        raise HTTPException(status_code=404, detail="Project or revision not found.")
    try:
        revision, summary = apply_edit_to_project(
            project_id=project_id,
            edit=SetDesignParameterEdit(parameter_id=parameter_id, value=request.value),
            user_instruction=request.instruction or f"Set design parameter {parameter_id}",
            store=store,
        )
        export_revision_stl(project_id, revision.revision_number, store=store)
        return {
            "project_id": project_id,
            "revision": revision_summary(revision).model_dump(mode="json"),
            "change_summary": summary,
        }
    except (EditApplicationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _current_model(project_id: str, store: ProjectStore) -> object:
    revision = store.current_revision(project_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="Project or revision not found.")
    return model_from_json(revision.model_type, revision.structured_spec_json)


def _escape_svg(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
