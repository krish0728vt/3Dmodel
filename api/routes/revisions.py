from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from projects.diff import diff_revisions
from projects.revisions import export_revision_stl, redo, restore, undo
from projects.store import ProjectStore

from api.dependencies import get_project_store
from api.schemas import DiffResponse, RevisionSummary
from api.utils import revision_summary


router = APIRouter(prefix="/api/projects", tags=["revisions"])


@router.post("/{project_id}/undo", response_model=RevisionSummary)
def undo_project(project_id: str, store: ProjectStore = Depends(get_project_store)) -> RevisionSummary:
    try:
        revision = undo(project_id, store=store)
        export_revision_stl(project_id, revision.revision_number, store=store)
        return revision_summary(revision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/redo", response_model=RevisionSummary)
def redo_project(project_id: str, store: ProjectStore = Depends(get_project_store)) -> RevisionSummary:
    try:
        revision = redo(project_id, store=store)
        export_revision_stl(project_id, revision.revision_number, store=store)
        return revision_summary(revision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/restore/{revision_number}", response_model=RevisionSummary)
def restore_project(
    project_id: str,
    revision_number: int,
    store: ProjectStore = Depends(get_project_store),
) -> RevisionSummary:
    try:
        revision = restore(project_id, revision_number, store=store)
        export_revision_stl(project_id, revision.revision_number, store=store)
        return revision_summary(revision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{project_id}/diff", response_model=DiffResponse)
def diff_project(
    project_id: str,
    from_revision: int,
    to_revision: int,
    store: ProjectStore = Depends(get_project_store),
) -> DiffResponse:
    try:
        diff = diff_revisions(project_id, from_revision, to_revision, store=store)
        return DiffResponse(
            project_id=project_id,
            from_revision=from_revision,
            to_revision=to_revision,
            diff=diff,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
