from __future__ import annotations

from fastapi.testclient import TestClient

from api.dependencies import get_learning_store, get_project_store
from api.server import create_app
from learning.store import LearningStore
from projects.store import ProjectStore


def test_operation_plan_preview_metadata_and_meshes(tmp_path) -> None:
    project_store = ProjectStore(tmp_path / "projects.db")
    learning_store = LearningStore(tmp_path / "learning.db")
    app = create_app()
    app.dependency_overrides[get_project_store] = lambda: project_store
    app.dependency_overrides[get_learning_store] = lambda: learning_store
    client = TestClient(app)

    project_id = _create_operation_project(client)

    response = client.get(f"/api/projects/{project_id}/revisions/1/preview")

    assert response.status_code == 200
    preview = response.json()
    assert preview["preview_format"] == "semantic-stl-preview"
    assert preview["overall_bounding_box"]["xlen"] > 0
    objects = {item["operation_id"]: item for item in preview["objects"]}
    assert {"base", "center_boss", "center_hole"}.issubset(objects)
    assert objects["base"]["mesh_url"].endswith("/api/projects/" + project_id + "/revisions/1/preview/base/mesh")
    assert objects["center_boss"]["object_type"] == "helper"
    assert objects["center_hole"]["object_type"] == "subtractive_helper"
    assert "helper geometry" in objects["center_hole"]["notes"]

    mesh_response = client.get(objects["center_boss"]["mesh_url"])
    assert mesh_response.status_code == 200
    assert len(mesh_response.content) > 0


def test_template_preview_falls_back_to_whole_model_selection(tmp_path) -> None:
    project_store = ProjectStore(tmp_path / "projects.db")
    learning_store = LearningStore(tmp_path / "learning.db")
    app = create_app()
    app.dependency_overrides[get_project_store] = lambda: project_store
    app.dependency_overrides[get_learning_store] = lambda: learning_store
    client = TestClient(app)

    generate_response = client.post(
        "/api/generate",
        json={
            "project_name": "Preview Box",
            "spec": {
                "part_type": "box",
                "width_mm": 20,
                "depth_mm": 12,
                "height_mm": 8,
                "corner_radius_mm": 0,
            },
        },
    )
    assert generate_response.status_code == 200
    project_id = generate_response.json()["project"]["project_id"]

    response = client.get(f"/api/projects/{project_id}/revisions/1/preview")

    assert response.status_code == 200
    preview = response.json()
    assert [item["operation_id"] for item in preview["objects"]] == ["model"]
    assert preview["objects"][0]["object_type"] == "final_solid"
    assert preview["objects"][0]["mesh_url"] == f"/api/projects/{project_id}/download/stl?revision=1"


def test_preview_api_returns_404_for_invalid_revision(tmp_path) -> None:
    project_store = ProjectStore(tmp_path / "projects.db")
    learning_store = LearningStore(tmp_path / "learning.db")
    app = create_app()
    app.dependency_overrides[get_project_store] = lambda: project_store
    app.dependency_overrides[get_learning_store] = lambda: learning_store
    client = TestClient(app)

    project_id = _create_operation_project(client)

    response = client.get(f"/api/projects/{project_id}/revisions/99/preview")

    assert response.status_code == 404


def _create_operation_project(client: TestClient) -> str:
    response = client.post(
        "/api/generate",
        json={
            "project_name": "Preview Operation Plan",
            "spec": {
                "schema_version": "1.1",
                "project_name": "preview_operation_plan",
                "operations": [
                    {
                        "id": "base",
                        "label": "Base Plate",
                        "operation_type": "create_box",
                        "width_mm": 60,
                        "depth_mm": 40,
                        "height_mm": 8,
                    },
                    {
                        "id": "center_boss",
                        "label": "Center Boss",
                        "operation_type": "boss",
                        "target_id": "base",
                        "position": [0, 0],
                        "diameter_mm": 18,
                        "height_mm": 10,
                    },
                    {
                        "id": "center_hole",
                        "label": "Center Hole",
                        "operation_type": "through_hole",
                        "target_id": "center_boss",
                        "position": [0, 0],
                        "hole_diameter_mm": 6,
                    },
                ],
                "final_object_id": "center_hole",
            },
        },
    )
    assert response.status_code == 200
    return response.json()["project"]["project_id"]
