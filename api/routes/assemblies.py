from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import ValidationError

from api.dependencies import get_assembly_store, get_project_store
from api.schemas import AssemblyCreateRequest, AssemblyEditRequest, DeleteConfirmRequest, DuplicateRequest, RenameRequest
from assemblies.manager import (
    ASSEMBLY_EDIT_ADAPTER,
    apply_assembly_edit,
    assembly_engineering,
    assembly_preview,
    create_assembly,
    export_combined_step,
    export_manifest,
    initialize_revision,
    parse_assembly_instruction,
    redo,
    restore,
    undo,
)
from assemblies.models import AssemblyComponent
from assemblies.store import AssemblyStore
from assemblies.validation import AssemblyValidationError
from projects.store import ProjectStore


router = APIRouter(prefix="/api/assemblies", tags=["assemblies"])


@router.get("")
def list_assemblies(
    search: str | None = None,
    status: str = Query("active", pattern="^(active|archived|all)$"),
    sort: str = Query("recently_updated", pattern="^(recently_updated|recently_opened|name|created)$"),
    store: AssemblyStore = Depends(get_assembly_store),
) -> list[dict[str, object]]:
    try:
        return [assembly.model_dump(mode="json") for assembly in store.list_assemblies(search=search, status=status, sort=sort)]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("")
def create_assembly_route(
    request: AssemblyCreateRequest,
    store: AssemblyStore = Depends(get_assembly_store),
    project_store: ProjectStore = Depends(get_project_store),
) -> dict[str, object]:
    try:
        assembly = create_assembly(name=request.name, notes=request.notes, store=store)
        revision = initialize_revision(assembly_id=assembly.assembly_id, components=request.components, store=store, project_store=project_store)
        assembly = store.get_assembly(assembly.assembly_id) or assembly
        return {"assembly": assembly.model_dump(mode="json"), "current_revision": revision.model_dump(mode="json")}
    except (AssemblyValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{assembly_id}")
def get_assembly_route(assembly_id: str, store: AssemblyStore = Depends(get_assembly_store)) -> dict[str, object]:
    assembly = store.get_assembly(assembly_id)
    if assembly is None:
        raise HTTPException(status_code=404, detail="Assembly not found.")
    store.mark_opened(assembly_id)
    assembly = store.get_assembly(assembly_id) or assembly
    revision = store.current_revision(assembly_id)
    return {
        "assembly": assembly.model_dump(mode="json"),
        "current_revision": revision.model_dump(mode="json") if revision else None,
    }


@router.patch("/{assembly_id}")
def rename_assembly_route(assembly_id: str, request: RenameRequest, store: AssemblyStore = Depends(get_assembly_store)) -> dict[str, object]:
    try:
        return store.rename_assembly(assembly_id, request.name).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{assembly_id}/rename")
def rename_assembly_legacy(assembly_id: str, request: RenameRequest, store: AssemblyStore = Depends(get_assembly_store)) -> dict[str, object]:
    return rename_assembly_route(assembly_id, request, store)


@router.post("/{assembly_id}/duplicate")
def duplicate_assembly_route(assembly_id: str, request: DuplicateRequest, store: AssemblyStore = Depends(get_assembly_store)) -> dict[str, object]:
    try:
        assembly, revision = store.duplicate_assembly(assembly_id, revision_number=request.revision, name=request.name)
        return {"assembly": assembly.model_dump(mode="json"), "current_revision": revision.model_dump(mode="json")}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{assembly_id}/archive")
def archive_assembly_route(assembly_id: str, store: AssemblyStore = Depends(get_assembly_store)) -> dict[str, object]:
    try:
        return store.archive_assembly(assembly_id).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{assembly_id}/unarchive")
def unarchive_assembly_route(assembly_id: str, store: AssemblyStore = Depends(get_assembly_store)) -> dict[str, object]:
    try:
        return store.unarchive_assembly(assembly_id).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{assembly_id}")
def delete_assembly_route(assembly_id: str, request: DeleteConfirmRequest, store: AssemblyStore = Depends(get_assembly_store)) -> dict[str, object]:
    try:
        result = store.delete_assembly(assembly_id)
        return {"assembly_id": assembly_id, "deleted": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{assembly_id}/thumbnail")
def assembly_thumbnail(assembly_id: str, store: AssemblyStore = Depends(get_assembly_store)) -> Response:
    assembly = store.get_assembly(assembly_id)
    if assembly is None:
        raise HTTPException(status_code=404, detail="Assembly not found.")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">
<rect width="320" height="180" fill="#101316"/>
<rect x="18" y="18" width="284" height="144" fill="#151b1f" stroke="#334047"/>
<path d="M66 116h68l20-32H86z" fill="#26343b" stroke="#8ae8fb"/>
<path d="M164 116h72l18-38h-72z" fill="#26343b" stroke="#8fa1a8"/>
<text x="28" y="44" fill="#8fa1a8" font-family="Arial" font-size="16">ASSEMBLY</text>
<text x="28" y="150" fill="#e8f0f2" font-family="Arial" font-size="18">{_escape_svg(assembly.name[:28])}</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/{assembly_id}/history")
def assembly_history(assembly_id: str, store: AssemblyStore = Depends(get_assembly_store)) -> list[dict[str, object]]:
    if store.get_assembly(assembly_id) is None:
        raise HTTPException(status_code=404, detail="Assembly not found.")
    return [revision.model_dump(mode="json") for revision in store.history(assembly_id)]


@router.post("/{assembly_id}/components")
def add_component(
    assembly_id: str,
    component: AssemblyComponent,
    store: AssemblyStore = Depends(get_assembly_store),
    project_store: ProjectStore = Depends(get_project_store),
) -> dict[str, object]:
    return _edit_response(
        assembly_id,
        {"edit_type": "add_component", "component": component.model_dump(mode="json")},
        "Add assembly component",
        store,
        project_store,
    )


@router.post("/{assembly_id}/edit")
def edit_assembly(
    assembly_id: str,
    request: AssemblyEditRequest,
    store: AssemblyStore = Depends(get_assembly_store),
    project_store: ProjectStore = Depends(get_project_store),
) -> dict[str, object]:
    if request.edit is not None:
        return _edit_response(assembly_id, request.edit, request.instruction or "Structured assembly edit", store, project_store)
    if request.instruction:
        current = store.current_revision(assembly_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Assembly revision not found.")
        try:
            edit = parse_assembly_instruction(request.instruction, current.components)
            return _edit_response(assembly_id, edit.model_dump(mode="json"), request.instruction, store, project_store)
        except AssemblyValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail="Provide instruction or structured edit.")


@router.post("/{assembly_id}/undo")
def undo_assembly(assembly_id: str, store: AssemblyStore = Depends(get_assembly_store)) -> dict[str, object]:
    try:
        return undo(assembly_id, store=store).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{assembly_id}/redo")
def redo_assembly(assembly_id: str, store: AssemblyStore = Depends(get_assembly_store)) -> dict[str, object]:
    try:
        return redo(assembly_id, store=store).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{assembly_id}/restore/{revision_number}")
def restore_assembly(assembly_id: str, revision_number: int, store: AssemblyStore = Depends(get_assembly_store)) -> dict[str, object]:
    try:
        return restore(assembly_id, revision_number, store=store).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{assembly_id}/preview")
def preview_assembly(
    assembly_id: str,
    revision: int | None = None,
    store: AssemblyStore = Depends(get_assembly_store),
    project_store: ProjectStore = Depends(get_project_store),
) -> dict[str, object]:
    try:
        return assembly_preview(assembly_id=assembly_id, revision_number=revision, store=store, project_store=project_store).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{assembly_id}/engineering")
def engineering_assembly(
    assembly_id: str,
    revision: int | None = None,
    store: AssemblyStore = Depends(get_assembly_store),
    project_store: ProjectStore = Depends(get_project_store),
) -> dict[str, object]:
    try:
        return assembly_engineering(assembly_id=assembly_id, revision_number=revision, store=store, project_store=project_store).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{assembly_id}/download")
def download_assembly(
    assembly_id: str,
    revision: int | None = None,
    format: str = "manifest",
    store: AssemblyStore = Depends(get_assembly_store),
    project_store: ProjectStore = Depends(get_project_store),
) -> FileResponse:
    try:
        if format == "step":
            path = export_combined_step(assembly_id=assembly_id, revision_number=revision, store=store, project_store=project_store)
            return FileResponse(path, media_type="model/step", filename=path.name)
        path = export_manifest(assembly_id=assembly_id, revision_number=revision, store=store)
        return FileResponse(path, media_type="application/json", filename=path.name)
    except (AssemblyValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _edit_response(
    assembly_id: str,
    raw_edit: dict[str, object],
    instruction: str,
    store: AssemblyStore,
    project_store: ProjectStore,
) -> dict[str, object]:
    try:
        edit = ASSEMBLY_EDIT_ADAPTER.validate_python(raw_edit)
        revision, summary = apply_assembly_edit(
            assembly_id=assembly_id,
            edit=edit,
            user_instruction=instruction,
            store=store,
            project_store=project_store,
        )
        return {
            "assembly_id": assembly_id,
            "revision": revision.model_dump(mode="json"),
            "change_summary": summary,
        }
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except (AssemblyValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _escape_svg(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
