from __future__ import annotations

from fastapi.testclient import TestClient

from api.dependencies import get_learning_store, get_project_store
from api.server import create_app
from learning.store import LearningStore
from projects.store import ProjectStore


def test_health_endpoint_reports_online() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "online"


def test_generate_project_history_edit_and_stl_download(tmp_path) -> None:
    project_store = ProjectStore(tmp_path / "projects.db")
    learning_store = LearningStore(tmp_path / "learning.db")
    app = create_app()
    app.dependency_overrides[get_project_store] = lambda: project_store
    app.dependency_overrides[get_learning_store] = lambda: learning_store
    client = TestClient(app)

    generate_response = client.post(
        "/api/generate",
        json={
            "project_name": "API Box",
            "spec": {
                "part_type": "box",
                "width_mm": 10,
                "depth_mm": 20,
                "height_mm": 5,
                "corner_radius_mm": 0,
            },
        },
    )

    assert generate_response.status_code == 200
    body = generate_response.json()
    project_id = body["project"]["project_id"]
    assert body["project"]["current_revision"] == 1
    assert body["revision"]["revision_number"] == 1
    assert body["stl_url"] == f"/api/projects/{project_id}/download/stl"

    history_response = client.get(f"/api/projects/{project_id}/history")
    assert history_response.status_code == 200
    assert [item["revision_number"] for item in history_response.json()] == [1]

    edit_response = client.post(
        f"/api/projects/{project_id}/edit",
        json={
            "instruction": "Make the box wider",
            "edit": {
                "edit_type": "set_parameter",
                "path": "width_mm",
                "value": 15,
            },
        },
    )

    assert edit_response.status_code == 200
    assert edit_response.json()["revision"]["revision_number"] == 2

    detail_response = client.get(f"/api/projects/{project_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["current_model"]["width_mm"] == 15

    stl_response = client.get(f"/api/projects/{project_id}/download/stl")
    assert stl_response.status_code == 200
    assert len(stl_response.content) > 0


def test_api_generates_and_edits_advanced_operation_plan(tmp_path) -> None:
    project_store = ProjectStore(tmp_path / "projects.db")
    learning_store = LearningStore(tmp_path / "learning.db")
    app = create_app()
    app.dependency_overrides[get_project_store] = lambda: project_store
    app.dependency_overrides[get_learning_store] = lambda: learning_store
    client = TestClient(app)

    response = client.post(
        "/api/generate",
        json={
            "project_name": "API Pocket",
            "spec": {
                "schema_version": "1.1",
                "project_name": "api_pocket",
                "operations": [
                    {
                        "id": "base",
                        "operation_type": "create_box",
                        "width_mm": 60,
                        "depth_mm": 40,
                        "height_mm": 8,
                    },
                    {
                        "id": "pocket_profile",
                        "operation_type": "create_sketch",
                        "sketch": {
                            "id": "pocket_profile",
                            "plane": "XY",
                            "origin": [0, 0, 4.1],
                            "closed": True,
                            "entities": [
                                {
                                    "entity_type": "rectangle",
                                    "width_mm": 28,
                                    "height_mm": 16,
                                }
                            ],
                        },
                    },
                    {
                        "id": "pocket",
                        "operation_type": "cut_extrude",
                        "target_id": "base",
                        "sketch_id": "pocket_profile",
                        "distance_mm": 2,
                        "extent_type": "blind",
                        "direction": "negative",
                    },
                ],
                "final_object_id": "pocket",
            },
        },
    )

    assert response.status_code == 200
    project_id = response.json()["project"]["project_id"]

    edit_response = client.post(
        f"/api/projects/{project_id}/edit",
        json={
            "instruction": "Make the pocket 2 mm deeper",
            "edit": {
                "edit_type": "modify_operation",
                "operation_id": "pocket",
                "changes": {"distance_mm": 4},
            },
        },
    )

    assert edit_response.status_code == 200
    assert edit_response.json()["revision"]["revision_number"] == 2


def test_materials_and_project_engineering_api(tmp_path) -> None:
    project_store = ProjectStore(tmp_path / "projects.db")
    learning_store = LearningStore(tmp_path / "learning.db")
    app = create_app()
    app.dependency_overrides[get_project_store] = lambda: project_store
    app.dependency_overrides[get_learning_store] = lambda: learning_store
    client = TestClient(app)

    materials_response = client.get("/api/materials")
    assert materials_response.status_code == 200
    assert any(material["material_id"] == "pla" for material in materials_response.json())

    generate_response = client.post(
        "/api/generate",
        json={
            "project_name": "Engineering Box",
            "spec": {
                "part_type": "box",
                "width_mm": 25.4,
                "depth_mm": 25.4,
                "height_mm": 10,
                "corner_radius_mm": 0,
            },
        },
    )
    assert generate_response.status_code == 200
    project_id = generate_response.json()["project"]["project_id"]

    assign_response = client.post(
        f"/api/projects/{project_id}/material",
        json={"material_id": "pla"},
    )
    assert assign_response.status_code == 200

    report_response = client.get(
        f"/api/projects/{project_id}/engineering",
        params={"process": "3d_printing", "display_units": "in"},
    )
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["material"]["material_id"] == "pla"
    assert report["mass_estimate"]["mass_g"] > 0
    assert report["display_metrics"]["length_unit"] == "in"
    assert report["display_metrics"]["x"] == 1

    invalid_material = client.get(f"/api/projects/{project_id}/engineering", params={"material": "badium"})
    assert invalid_material.status_code == 400

    invalid_revision = client.get(f"/api/projects/{project_id}/engineering", params={"revision": 99})
    assert invalid_revision.status_code == 404
