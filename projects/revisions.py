from __future__ import annotations

from pathlib import Path

from cad.generator import generate_step, generate_stl
from projects.models import RevisionRecord
from projects.serialization import model_from_json
from projects.store import ProjectStore


def revision_output_path(project_id: str, revision_number: int) -> Path:
    return Path("outputs") / "projects" / project_id / f"revision_{revision_number:03d}.step"


def revision_stl_output_path(project_id: str, revision_number: int) -> Path:
    return Path("outputs") / "projects" / project_id / f"revision_{revision_number:03d}.stl"


def export_revision(
    project_id: str,
    revision_number: int | None = None,
    *,
    store: ProjectStore | None = None,
) -> Path:
    store = store or ProjectStore()
    revision = (
        store.current_revision(project_id)
        if revision_number is None
        else store.get_revision(project_id, revision_number)
    )
    if revision is None:
        raise ValueError("Revision not found.")
    model = model_from_json(revision.model_type, revision.structured_spec_json)
    output_path = revision_output_path(project_id, revision.revision_number)
    generate_step(model, output_path)
    generate_step(model, "outputs/model.step")
    return output_path


def export_revision_stl(
    project_id: str,
    revision_number: int | None = None,
    *,
    store: ProjectStore | None = None,
) -> Path:
    store = store or ProjectStore()
    revision = (
        store.current_revision(project_id)
        if revision_number is None
        else store.get_revision(project_id, revision_number)
    )
    if revision is None:
        raise ValueError("Revision not found.")
    model = model_from_json(revision.model_type, revision.structured_spec_json)
    output_path = revision_stl_output_path(project_id, revision.revision_number)
    generate_stl(model, output_path)
    generate_stl(model, "outputs/model.stl")
    return output_path


def undo(project_id: str, *, store: ProjectStore | None = None) -> RevisionRecord:
    store = store or ProjectStore()
    current = store.current_revision(project_id)
    if current is None or current.parent_revision_id is None:
        raise ValueError("No parent revision to undo to.")
    parent = _get_revision_by_id(store, project_id, current.parent_revision_id)
    return store.set_current_revision(project_id, parent.revision_number)


def redo(project_id: str, *, store: ProjectStore | None = None) -> RevisionRecord:
    store = store or ProjectStore()
    current = store.current_revision(project_id)
    if current is None:
        raise ValueError("Project has no current revision.")
    children = [rev for rev in store.history(project_id) if rev.parent_revision_id == current.revision_id]
    if not children:
        raise ValueError("No child revision to redo to.")
    return store.set_current_revision(project_id, children[-1].revision_number)


def restore(project_id: str, revision_number: int, *, store: ProjectStore | None = None) -> RevisionRecord:
    store = store or ProjectStore()
    revision = store.set_current_revision(project_id, revision_number)
    export_revision(project_id, revision_number, store=store)
    return revision


def _get_revision_by_id(store: ProjectStore, project_id: str, revision_id: str) -> RevisionRecord:
    for revision in store.history(project_id):
        if revision.revision_id == revision_id:
            return revision
    raise ValueError(f"Revision id not found: {revision_id}")
