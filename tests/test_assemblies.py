from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from ai.schemas import BoxSpec
from api.dependencies import get_assembly_store, get_project_store
from api.server import create_app
from assemblies.manager import (
    apply_assembly_edit,
    assembly_engineering,
    assembly_preview,
    create_assembly,
    export_manifest,
    initialize_revision,
    parse_assembly_instruction,
    redo,
    restore,
    undo,
)
from assemblies.models import (
    AddComponentEdit,
    AssemblyComponent,
    ComponentSourceType,
    MoveComponentEdit,
    SetGroundedEdit,
    SetVisibilityEdit,
    Transform,
)
from assemblies.store import AssemblyStore
from assemblies.validation import AssemblyValidationError
from learning.classifier import classify_failure
from learning.models import FailureCategory
from projects.manager import create_project_from_model
from projects.store import ProjectStore


def project_store(tmp_path) -> ProjectStore:
    return ProjectStore(tmp_path / "projects.db")


def assembly_store(tmp_path) -> AssemblyStore:
    return AssemblyStore(tmp_path / "assemblies.db")


def make_box_project(tmp_path, *, name: str = "Box", width: float = 10, material: str | None = None) -> tuple[ProjectStore, str]:
    store = project_store(tmp_path)
    project, _ = create_project_from_model(
        name=name,
        model=BoxSpec(width_mm=width, depth_mm=10, height_mm=5),
        source_prompt=name,
        store=store,
    )
    if material:
        store.set_material_assignment(project.project_id, material)
    return store, project.project_id


def component(component_id: str, project_id: str, *, x: float = 0, grounded: bool = False) -> AssemblyComponent:
    return AssemblyComponent(
        component_id=component_id,
        name=component_id.replace("_", " ").title(),
        source_type=ComponentSourceType.PROJECT_REVISION,
        project_id=project_id,
        project_revision=1,
        transform=Transform(translation_x_mm=x),
        grounded=grounded,
    )


def test_create_edit_history_undo_redo_restore_and_manifest(tmp_path) -> None:
    projects, project_id = make_box_project(tmp_path)
    assemblies = assembly_store(tmp_path)
    assembly = create_assembly(name="Two Box Fixture", store=assemblies)
    rev1 = initialize_revision(
        assembly_id=assembly.assembly_id,
        components=[component("base_box", project_id, grounded=True)],
        store=assemblies,
        project_store=projects,
    )

    rev2, summary = apply_assembly_edit(
        assembly_id=assembly.assembly_id,
        edit=AddComponentEdit(component=component("cover_box", project_id, x=20)),
        user_instruction="add cover",
        store=assemblies,
        project_store=projects,
    )
    rev3, _ = apply_assembly_edit(
        assembly_id=assembly.assembly_id,
        edit=MoveComponentEdit(component_id="cover_box", dx_mm=5),
        user_instruction="move cover",
        store=assemblies,
        project_store=projects,
    )

    assert rev1.revision_number == 1
    assert rev2.revision_number == 2
    assert rev3.revision_number == 3
    assert "Added component" in summary
    assert rev1.components == [component("base_box", project_id, grounded=True)]
    assert assemblies.current_revision(assembly.assembly_id).revision_number == 3
    assert assemblies.current_revision(assembly.assembly_id).components[1].transform.translation_x_mm == 25

    assert undo(assembly.assembly_id, store=assemblies).revision_number == 2
    assert redo(assembly.assembly_id, store=assemblies).revision_number == 3
    assert restore(assembly.assembly_id, 1, store=assemblies).revision_number == 1

    manifest_path = export_manifest(assembly_id=assembly.assembly_id, revision_number=3, store=assemblies)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["revision"] == 3
    assert [item["component_id"] for item in manifest["components"]] == ["base_box", "cover_box"]


def test_grounded_components_reject_transform_edits(tmp_path) -> None:
    projects, project_id = make_box_project(tmp_path)
    assemblies = assembly_store(tmp_path)
    assembly = create_assembly(name="Grounded Fixture", store=assemblies)
    initialize_revision(
        assembly_id=assembly.assembly_id,
        components=[component("base_box", project_id, grounded=True)],
        store=assemblies,
        project_store=projects,
    )

    with pytest.raises(AssemblyValidationError, match="grounded"):
        apply_assembly_edit(
            assembly_id=assembly.assembly_id,
            edit=MoveComponentEdit(component_id="base_box", dx_mm=5),
            user_instruction="move base",
            store=assemblies,
            project_store=projects,
        )

    assert assemblies.current_revision(assembly.assembly_id).revision_number == 1


def test_preview_engineering_visibility_and_interference(tmp_path) -> None:
    projects, project_id = make_box_project(tmp_path, material="pla")
    assemblies = assembly_store(tmp_path)
    assembly = create_assembly(name="Interference Fixture", store=assemblies)
    initialize_revision(
        assembly_id=assembly.assembly_id,
        components=[
            component("left_box", project_id, x=0),
            component("right_box", project_id, x=5),
        ],
        store=assemblies,
        project_store=projects,
    )

    preview = assembly_preview(assembly_id=assembly.assembly_id, store=assemblies, project_store=projects)
    assert preview.bounding_box is not None
    assert preview.bounding_box.xlen == pytest.approx(15)
    assert all(item.mesh_url for item in preview.components)

    engineering = assembly_engineering(assembly_id=assembly.assembly_id, store=assemblies, project_store=projects)
    assert engineering.known_mass_g > 0
    assert engineering.center_of_mass_status == "available"
    assert len(engineering.component_summaries) == 2
    assert engineering.interferences[0].status.value == "POSSIBLE_OVERLAP"

    apply_assembly_edit(
        assembly_id=assembly.assembly_id,
        edit=SetVisibilityEdit(component_id="right_box", visible=False),
        user_instruction="hide right",
        store=assemblies,
        project_store=projects,
    )
    hidden = assembly_preview(assembly_id=assembly.assembly_id, store=assemblies, project_store=projects)
    assert hidden.components[1].visible is False


def test_instruction_parser_and_classifier(tmp_path) -> None:
    _, project_id = make_box_project(tmp_path)
    parts = [component("cover_box", project_id)]

    edit = parse_assembly_instruction("move cover box 12 mm higher", parts)
    assert isinstance(edit, MoveComponentEdit)
    assert edit.dz_mm == 12

    grounded = AssemblyValidationError("Component 'cover_box' is grounded.")
    missing = AssemblyValidationError("cover_box references unknown project.")
    export = AssemblyValidationError("Assembly export requires at least one component.")

    assert classify_failure(grounded) == FailureCategory.ASSEMBLY_TRANSFORM_FAILURE
    assert classify_failure(missing) == FailureCategory.ASSEMBLY_REFERENCE_FAILURE
    assert classify_failure(export) == FailureCategory.ASSEMBLY_EXPORT_FAILURE


def test_assembly_api_create_edit_preview_engineering_and_download(tmp_path) -> None:
    projects, project_id = make_box_project(tmp_path, material="pla")
    assemblies = assembly_store(tmp_path)
    app = create_app()
    app.dependency_overrides[get_project_store] = lambda: projects
    app.dependency_overrides[get_assembly_store] = lambda: assemblies
    client = TestClient(app)

    response = client.post(
        "/api/assemblies",
        json={
            "name": "API Assembly",
            "components": [
                {
                    "component_id": "base_box",
                    "name": "Base Box",
                    "source_type": "project_revision",
                    "project_id": project_id,
                    "project_revision": 1,
                    "grounded": True,
                }
            ],
        },
    )
    assert response.status_code == 200
    assembly_id = response.json()["assembly"]["assembly_id"]

    add_response = client.post(
        f"/api/assemblies/{assembly_id}/components",
        json={
            "component_id": "cover_box",
            "name": "Cover Box",
            "source_type": "project_revision",
            "project_id": project_id,
            "project_revision": 1,
            "transform": {"translation_x_mm": 20},
        },
    )
    assert add_response.status_code == 200
    assert add_response.json()["revision"]["revision_number"] == 2

    edit_response = client.post(
        f"/api/assemblies/{assembly_id}/edit",
        json={"edit": {"edit_type": "move_component", "component_id": "cover_box", "dx_mm": 5}},
    )
    assert edit_response.status_code == 200

    preview_response = client.get(f"/api/assemblies/{assembly_id}/preview")
    assert preview_response.status_code == 200
    assert len(preview_response.json()["components"]) == 2

    engineering_response = client.get(f"/api/assemblies/{assembly_id}/engineering")
    assert engineering_response.status_code == 200
    assert engineering_response.json()["known_mass_g"] > 0

    download_response = client.get(f"/api/assemblies/{assembly_id}/download")
    assert download_response.status_code == 200
    assert b"cover_box" in download_response.content

    client.post(
        f"/api/assemblies/{assembly_id}/edit",
        json={"edit": {"edit_type": "set_grounded", "component_id": "cover_box", "grounded": True}},
    )
    blocked = client.post(
        f"/api/assemblies/{assembly_id}/edit",
        json={"edit": {"edit_type": "move_component", "component_id": "cover_box", "dx_mm": 1}},
    )
    assert blocked.status_code == 400
