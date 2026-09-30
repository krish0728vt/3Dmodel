from __future__ import annotations

from pathlib import Path

from assemblies.models import AssemblyComponent, ComponentSourceType, Transform
from projects.store import ProjectStore


class AssemblyValidationError(ValueError):
    """Raised when an assembly or component reference is invalid."""


def validate_components(components: list[AssemblyComponent], *, project_store: ProjectStore) -> None:
    errors: list[str] = []
    seen: set[str] = set()
    for component in components:
        if not component.component_id.strip():
            errors.append("component_id must not be empty.")
        if component.component_id in seen:
            errors.append(f"Duplicate component_id: {component.component_id}.")
        seen.add(component.component_id)
        errors.extend(_validate_source(component, project_store))
        errors.extend(_validate_transform(component.transform, component.component_id))
    if errors:
        raise AssemblyValidationError("Invalid assembly: " + " ".join(errors))


def require_non_empty(components: list[AssemblyComponent]) -> None:
    if not components:
        raise AssemblyValidationError("Assembly export requires at least one component.")


def _validate_source(component: AssemblyComponent, project_store: ProjectStore) -> list[str]:
    errors: list[str] = []
    if component.source_type == ComponentSourceType.PROJECT_REVISION:
        if not component.project_id:
            return [f"{component.component_id} project_id is required."]
        project = project_store.get_project(component.project_id)
        if project is None:
            return [f"{component.component_id} references unknown project {component.project_id}."]
        revision_number = component.project_revision or project.current_revision
        if revision_number == 0 or project_store.get_revision(component.project_id, revision_number) is None:
            errors.append(f"{component.component_id} references missing revision {revision_number}.")
    elif component.source_type in {ComponentSourceType.GENERATED_FILE, ComponentSourceType.CAPABILITY_OUTPUT, ComponentSourceType.IMPORTED_FILE}:
        if not component.external_step_path and not component.external_stl_path:
            errors.append(f"{component.component_id} requires external_step_path or external_stl_path.")
        for path in [component.external_step_path, component.external_stl_path]:
            if path and not Path(path).exists():
                errors.append(f"{component.component_id} file does not exist: {path}.")
    return errors


def _validate_transform(transform: Transform, component_id: str) -> list[str]:
    values = transform.model_dump().values()
    if not all(isinstance(value, (int, float)) for value in values):
        return [f"{component_id} transform values must be numeric."]
    return []
