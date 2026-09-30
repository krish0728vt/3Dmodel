from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from assemblies.models import (
    AddComponentEdit,
    AssemblyComponent,
    AssemblyEdit,
    AssemblyEngineeringSummary,
    AssemblyPreview,
    AssemblyRecord,
    AssemblyRevisionRecord,
    ComponentEngineeringSummary,
    ComponentPreview,
    ComponentSourceType,
    InterferenceResult,
    InterferenceStatus,
    MoveComponentEdit,
    RemoveComponentEdit,
    RenameAssemblyEdit,
    RenameComponentEdit,
    RotateComponentEdit,
    SetGroundedEdit,
    SetTransformEdit,
    SetVisibilityEdit,
    Transform,
)
from assemblies.store import AssemblyStore
from assemblies.transforms import apply_transform, bbox_from_cadquery, boxes_overlap, merge_bounding_boxes, transform_bounding_box, transform_point
from assemblies.validation import AssemblyValidationError, require_non_empty, validate_components
from cad.generator import generate_workplane
from cad.operations import export_step, export_stl
from engineering.analyzer import analyze_part
from projects.revisions import export_revision_stl
from projects.serialization import model_from_json
from projects.store import ProjectStore


ASSEMBLY_EDIT_ADAPTER = TypeAdapter(AssemblyEdit)


def create_assembly(*, name: str, notes: str | None = None, store: AssemblyStore | None = None) -> AssemblyRecord:
    return (store or AssemblyStore()).create_assembly(name=name, notes=notes)


def initialize_revision(
    *,
    assembly_id: str,
    components: list[AssemblyComponent] | None = None,
    store: AssemblyStore | None = None,
    project_store: ProjectStore | None = None,
) -> AssemblyRevisionRecord:
    store = store or AssemblyStore()
    project_store = project_store or ProjectStore()
    components = components or []
    validate_components(components, project_store=project_store)
    return store.add_revision(
        assembly_id=assembly_id,
        components=components,
        user_instruction="Initial assembly",
        change_summary="Initial assembly",
        parent_revision_id=None,
    )


def apply_assembly_edit(
    *,
    assembly_id: str,
    edit: AssemblyEdit,
    user_instruction: str,
    store: AssemblyStore | None = None,
    project_store: ProjectStore | None = None,
) -> tuple[AssemblyRevisionRecord, str]:
    store = store or AssemblyStore()
    project_store = project_store or ProjectStore()
    current = store.current_revision(assembly_id)
    if current is None:
        current = initialize_revision(assembly_id=assembly_id, store=store, project_store=project_store)
    components = deepcopy(current.components)
    summary = _apply_edit_components(assembly_id, components, edit, store=store)
    validate_components(components, project_store=project_store)
    revision = store.add_revision(
        assembly_id=assembly_id,
        components=components,
        user_instruction=user_instruction,
        change_summary=summary,
        parent_revision_id=current.revision_id,
    )
    return revision, summary


def parse_assembly_instruction(instruction: str, components: list[AssemblyComponent]) -> AssemblyEdit:
    """Small deterministic command parser for common assembly chat edits."""

    lowered = instruction.lower()
    component = _component_from_text(lowered, components)
    if component is None:
        raise AssemblyValidationError("Could not identify a component in the assembly instruction.")
    number = _first_number(lowered) or 0
    axis = "z" if " z" in lowered or "higher" in lowered or "up" in lowered else "x" if " x" in lowered else "y" if " y" in lowered else "z"
    if "hide" in lowered:
        return SetVisibilityEdit(component_id=component.component_id, visible=False)
    if "show" in lowered:
        return SetVisibilityEdit(component_id=component.component_id, visible=True)
    if "ground" in lowered:
        return SetGroundedEdit(component_id=component.component_id, grounded=True)
    if "rotate" in lowered:
        return RotateComponentEdit(component_id=component.component_id, rz_deg=number if axis == "z" else 0, rx_deg=number if axis == "x" else 0, ry_deg=number if axis == "y" else 0)
    if "move" in lowered or "higher" in lowered or "up" in lowered:
        sign = -1 if "down" in lowered or "lower" in lowered else 1
        return MoveComponentEdit(
            component_id=component.component_id,
            dx_mm=sign * number if axis == "x" else 0,
            dy_mm=sign * number if axis == "y" else 0,
            dz_mm=sign * number if axis == "z" else 0,
        )
    raise AssemblyValidationError("Unsupported assembly instruction.")


def assembly_preview(
    *,
    assembly_id: str,
    revision_number: int | None = None,
    store: AssemblyStore | None = None,
    project_store: ProjectStore | None = None,
) -> AssemblyPreview:
    store = store or AssemblyStore()
    project_store = project_store or ProjectStore()
    revision = _revision(store, assembly_id, revision_number)
    previews: list[ComponentPreview] = []
    boxes = []
    for component in revision.components:
        box = None
        try:
            part = _component_workplane(component, project_store)
            box = transform_bounding_box(bbox_from_cadquery(part), component.transform)
            boxes.append(box)
        except Exception:
            box = None
        previews.append(
            ComponentPreview(
                component_id=component.component_id,
                name=component.name,
                source_type=component.source_type,
                mesh_url=_component_mesh_url(component, project_store),
                transform=component.transform,
                visible=component.visible,
                grounded=component.grounded,
                bounding_box=box,
            )
        )
    return AssemblyPreview(
        assembly_id=assembly_id,
        revision=revision.revision_number,
        components=previews,
        bounding_box=merge_bounding_boxes(boxes),
    )


def assembly_engineering(
    *,
    assembly_id: str,
    revision_number: int | None = None,
    store: AssemblyStore | None = None,
    project_store: ProjectStore | None = None,
) -> AssemblyEngineeringSummary:
    store = store or AssemblyStore()
    project_store = project_store or ProjectStore()
    revision = _revision(store, assembly_id, revision_number)
    preview = assembly_preview(assembly_id=assembly_id, revision_number=revision.revision_number, store=store, project_store=project_store)
    component_summaries: list[ComponentEngineeringSummary] = []
    known_mass = 0.0
    weighted = [0.0, 0.0, 0.0]
    unknown: list[str] = []
    for component in revision.components:
        mass = None
        com = None
        material_id = None
        try:
            report = _component_engineering(component, project_store)
            material_id = report.material.material_id if report.material else None
            if report.mass_estimate is not None:
                mass = report.mass_estimate.mass_g
                local = report.geometry_metrics.center_of_mass
                com = transform_point((local.x_mm, local.y_mm, local.z_mm), component.transform)
                known_mass += mass
                weighted[0] += com[0] * mass
                weighted[1] += com[1] * mass
                weighted[2] += com[2] * mass
            else:
                unknown.append(component.component_id)
        except Exception:
            unknown.append(component.component_id)
        box = next((item.bounding_box for item in preview.components if item.component_id == component.component_id), None)
        component_summaries.append(ComponentEngineeringSummary(component_id=component.component_id, name=component.name, bounding_box=box, mass_g=mass, center_of_mass=com, material_id=material_id))
    center_status = "available" if known_mass > 0 and not unknown else "partial" if known_mass > 0 else "unavailable"
    center = (weighted[0] / known_mass, weighted[1] / known_mass, weighted[2] / known_mass) if center_status == "available" else None
    return AssemblyEngineeringSummary(
        assembly_id=assembly_id,
        revision=revision.revision_number,
        component_count=len(revision.components),
        component_summaries=component_summaries,
        bounding_box=preview.bounding_box,
        known_mass_g=known_mass,
        unknown_mass_components=unknown,
        center_of_mass=center,
        center_of_mass_status=center_status,  # type: ignore[arg-type]
        interferences=check_interferences(preview),
    )


def check_interferences(preview: AssemblyPreview) -> list[InterferenceResult]:
    results: list[InterferenceResult] = []
    components = [component for component in preview.components if component.visible and component.bounding_box is not None]
    for index, first in enumerate(components):
        for second in components[index + 1 :]:
            status = InterferenceStatus.POSSIBLE_OVERLAP if boxes_overlap(first.bounding_box, second.bounding_box) else InterferenceStatus.NO_OVERLAP  # type: ignore[arg-type]
            if status != InterferenceStatus.NO_OVERLAP:
                results.append(InterferenceResult(first_component_id=first.component_id, second_component_id=second.component_id, status=status))
    return results


def export_manifest(
    *,
    assembly_id: str,
    revision_number: int | None = None,
    store: AssemblyStore | None = None,
) -> Path:
    store = store or AssemblyStore()
    revision = _revision(store, assembly_id, revision_number)
    path = Path("outputs") / "assemblies" / assembly_id / f"revision_{revision.revision_number:03d}.manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "assembly_id": assembly_id,
        "revision": revision.revision_number,
        "components": [component.model_dump(mode="json") for component in revision.components],
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def export_combined_step(
    *,
    assembly_id: str,
    revision_number: int | None = None,
    store: AssemblyStore | None = None,
    project_store: ProjectStore | None = None,
) -> Path:
    store = store or AssemblyStore()
    project_store = project_store or ProjectStore()
    revision = _revision(store, assembly_id, revision_number)
    require_non_empty(revision.components)
    compound = None
    for component in revision.components:
        if not component.visible:
            continue
        transformed = apply_transform(_component_workplane(component, project_store), component.transform)
        compound = transformed if compound is None else compound.union(transformed)
    if compound is None:
        raise AssemblyValidationError("Assembly export requires at least one visible component.")
    path = Path("outputs") / "assemblies" / assembly_id / f"revision_{revision.revision_number:03d}.step"
    return export_step(compound, path)


def export_combined_stl(
    *,
    assembly_id: str,
    revision_number: int | None = None,
    store: AssemblyStore | None = None,
    project_store: ProjectStore | None = None,
) -> Path:
    store = store or AssemblyStore()
    project_store = project_store or ProjectStore()
    revision = _revision(store, assembly_id, revision_number)
    require_non_empty(revision.components)
    compound = None
    for component in revision.components:
        if not component.visible:
            continue
        transformed = apply_transform(_component_workplane(component, project_store), component.transform)
        compound = transformed if compound is None else compound.union(transformed)
    if compound is None:
        raise AssemblyValidationError("Assembly export requires at least one visible component.")
    path = Path("outputs") / "assemblies" / assembly_id / f"revision_{revision.revision_number:03d}.stl"
    return export_stl(compound, path)


def undo(assembly_id: str, *, store: AssemblyStore | None = None) -> AssemblyRevisionRecord:
    store = store or AssemblyStore()
    current = store.current_revision(assembly_id)
    if current is None or current.parent_revision_id is None:
        raise ValueError("No parent revision to undo to.")
    for revision in store.history(assembly_id):
        if revision.revision_id == current.parent_revision_id:
            return store.set_current_revision(assembly_id, revision.revision_number)
    raise ValueError("Parent revision not found.")


def redo(assembly_id: str, *, store: AssemblyStore | None = None) -> AssemblyRevisionRecord:
    store = store or AssemblyStore()
    current = store.current_revision(assembly_id)
    if current is None:
        raise ValueError("Assembly has no current revision.")
    children = [revision for revision in store.history(assembly_id) if revision.parent_revision_id == current.revision_id]
    if not children:
        raise ValueError("No child revision to redo to.")
    return store.set_current_revision(assembly_id, children[-1].revision_number)


def restore(assembly_id: str, revision_number: int, *, store: AssemblyStore | None = None) -> AssemblyRevisionRecord:
    return (store or AssemblyStore()).set_current_revision(assembly_id, revision_number)


def _apply_edit_components(assembly_id: str, components: list[AssemblyComponent], edit: AssemblyEdit, *, store: AssemblyStore) -> str:
    if isinstance(edit, AddComponentEdit):
        components.append(edit.component)
        return f"Added component {edit.component.name}"
    if isinstance(edit, RemoveComponentEdit):
        component = _component(components, edit.component_id)
        components.remove(component)
        return f"Removed component {component.name}"
    if isinstance(edit, MoveComponentEdit):
        component = _movable_component(components, edit.component_id)
        component.transform.translation_x_mm += edit.dx_mm
        component.transform.translation_y_mm += edit.dy_mm
        component.transform.translation_z_mm += edit.dz_mm
        return f"Moved {component.name}"
    if isinstance(edit, RotateComponentEdit):
        component = _movable_component(components, edit.component_id)
        component.transform.rotation_x_deg += edit.rx_deg
        component.transform.rotation_y_deg += edit.ry_deg
        component.transform.rotation_z_deg += edit.rz_deg
        return f"Rotated {component.name}"
    if isinstance(edit, SetTransformEdit):
        component = _movable_component(components, edit.component_id)
        component.transform = edit.transform
        return f"Set transform for {component.name}"
    if isinstance(edit, SetVisibilityEdit):
        component = _component(components, edit.component_id)
        component.visible = edit.visible
        return f"Set visibility for {component.name}"
    if isinstance(edit, SetGroundedEdit):
        component = _component(components, edit.component_id)
        component.grounded = edit.grounded
        return f"Set grounded for {component.name}"
    if isinstance(edit, RenameComponentEdit):
        component = _component(components, edit.component_id)
        old = component.name
        component.name = edit.name
        return f"Renamed {old} to {edit.name}"
    if isinstance(edit, RenameAssemblyEdit):
        store.rename_assembly(assembly_id, edit.name)
        return f"Renamed assembly to {edit.name}"
    raise AssemblyValidationError(f"Unsupported assembly edit: {type(edit).__name__}")


def _component(components: list[AssemblyComponent], component_id: str) -> AssemblyComponent:
    for component in components:
        if component.component_id == component_id:
            return component
    raise AssemblyValidationError(f"Unknown component: {component_id}")


def _movable_component(components: list[AssemblyComponent], component_id: str) -> AssemblyComponent:
    component = _component(components, component_id)
    if component.grounded:
        raise AssemblyValidationError(f"Component '{component_id}' is grounded.")
    return component


def _component_workplane(component: AssemblyComponent, project_store: ProjectStore):
    if component.source_type == ComponentSourceType.PROJECT_REVISION:
        if not component.project_id:
            raise AssemblyValidationError(f"{component.component_id} missing project_id.")
        project = project_store.get_project(component.project_id)
        revision_number = component.project_revision or (project.current_revision if project else 0)
        revision = project_store.get_revision(component.project_id, revision_number)
        if revision is None:
            raise AssemblyValidationError(f"{component.component_id} source revision not found.")
        model = model_from_json(revision.model_type, revision.structured_spec_json)
        return generate_workplane(model)
    if component.external_step_path:
        import cadquery as cq

        return cq.importers.importStep(component.external_step_path)
    raise AssemblyValidationError(f"{component.component_id} has no loadable geometry source.")


def _component_engineering(component: AssemblyComponent, project_store: ProjectStore):
    if component.source_type != ComponentSourceType.PROJECT_REVISION or not component.project_id:
        raise AssemblyValidationError("Only project revision components have engineering reports in this milestone.")
    project = project_store.get_project(component.project_id)
    revision_number = component.project_revision or (project.current_revision if project else 0)
    revision = project_store.get_revision(component.project_id, revision_number)
    if revision is None:
        raise AssemblyValidationError("Component revision not found.")
    material_id = project_store.get_material_assignment(component.project_id)
    model = model_from_json(revision.model_type, revision.structured_spec_json)
    return analyze_part(model, project_id=component.project_id, revision_number=revision.revision_number, material_id=material_id)


def _component_mesh_url(component: AssemblyComponent, project_store: ProjectStore) -> str | None:
    if component.source_type == ComponentSourceType.PROJECT_REVISION and component.project_id:
        project = project_store.get_project(component.project_id)
        revision = component.project_revision or (project.current_revision if project else None)
        if revision:
            try:
                export_revision_stl(component.project_id, revision, store=project_store)
            except Exception:
                pass
            return f"/api/projects/{component.project_id}/download/stl?revision={revision}"
    if component.external_stl_path:
        return component.external_stl_path
    return None


def _revision(store: AssemblyStore, assembly_id: str, revision_number: int | None) -> AssemblyRevisionRecord:
    revision = store.current_revision(assembly_id) if revision_number is None else store.get_revision(assembly_id, revision_number)
    if revision is None:
        raise ValueError("Assembly revision not found.")
    return revision


def _component_from_text(text: str, components: list[AssemblyComponent]) -> AssemblyComponent | None:
    for component in components:
        if component.component_id.lower() in text or component.name.lower() in text:
            return component
    return None


def _first_number(text: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None
