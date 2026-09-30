from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ai.schemas import BoxSpec
from api.dependencies import get_assembly_store, get_project_store
from api.server import create_app
from assemblies.manager import create_assembly, initialize_revision
from assemblies.models import AssemblyComponent, ComponentSourceType
from assemblies.store import AssemblyStore
from projects.manager import create_project_from_model
from projects.models import ProjectStatus
from projects.store import ProjectStore


def project_store(tmp_path) -> ProjectStore:
    return ProjectStore(tmp_path / "projects.db")


def assembly_store(tmp_path) -> AssemblyStore:
    return AssemblyStore(tmp_path / "assemblies.db")


def make_project(tmp_path, *, name: str = "Workflow Box") -> tuple[ProjectStore, str]:
    store = project_store(tmp_path)
    project, _ = create_project_from_model(
        name=name,
        model=BoxSpec(width_mm=10, depth_mm=12, height_mm=4),
        source_prompt="workflow test",
        store=store,
    )
    return store, project.project_id


def test_project_lifecycle_search_sort_last_opened_and_delete(tmp_path) -> None:
    store, project_id = make_project(tmp_path, name="Motor Mount")
    original = store.get_project(project_id)
    assert original is not None

    renamed = store.rename_project(project_id, "Motor Mount Rev A")
    assert renamed.name == "Motor Mount Rev A"
    assert store.current_revision(project_id).revision_number == 1

    duplicate, duplicate_revision = store.duplicate_project(project_id)
    assert duplicate.project_id != project_id
    assert duplicate_revision.revision_number == 1
    assert duplicate_revision.structured_spec_json == store.current_revision(project_id).structured_spec_json

    store.mark_opened(duplicate.project_id)
    recent = store.list_projects(sort="recently_opened", status="all")
    assert recent[0].project_id == duplicate.project_id

    assert [project.project_id for project in store.list_projects(search="mount", status="all")]
    archived = store.archive_project(project_id)
    assert archived.status == ProjectStatus.ARCHIVED
    assert all(project.project_id != project_id for project in store.list_projects(status="active"))
    assert any(project.project_id == project_id for project in store.list_projects(status="archived"))
    assert store.unarchive_project(project_id).status == ProjectStatus.ACTIVE

    output_dir = Path("outputs") / "projects" / duplicate.project_id
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "scratch.txt").write_text("delete me", encoding="utf-8")
    result = store.delete_project(duplicate.project_id)
    assert result["revision_count"] == 1
    assert result["file_count"] >= 1
    assert store.get_project(duplicate.project_id) is None
    assert not output_dir.exists()
    assert store.get_project(project_id) is not None


def test_project_lifecycle_api(tmp_path) -> None:
    store, project_id = make_project(tmp_path, name="API Lifecycle Box")
    app = create_app()
    app.dependency_overrides[get_project_store] = lambda: store
    client = TestClient(app)

    rename = client.post(f"/api/projects/{project_id}/rename", json={"name": "Renamed API Box"})
    assert rename.status_code == 200
    assert rename.json()["name"] == "Renamed API Box"

    detail = client.get(f"/api/projects/{project_id}")
    assert detail.status_code == 200
    assert store.get_project(project_id).last_opened_at is not None

    duplicate = client.post(f"/api/projects/{project_id}/duplicate", json={})
    assert duplicate.status_code == 200
    duplicate_id = duplicate.json()["project_id"]
    assert duplicate_id != project_id

    search = client.get("/api/projects", params={"search": "renamed", "status": "all", "sort": "name"})
    assert search.status_code == 200
    assert any(item["project_id"] == project_id for item in search.json())

    archive = client.post(f"/api/projects/{project_id}/archive")
    assert archive.status_code == 200
    assert archive.json()["status"] == "archived"
    active = client.get("/api/projects", params={"status": "active"})
    assert all(item["project_id"] != project_id for item in active.json())

    unarchive = client.post(f"/api/projects/{project_id}/unarchive")
    assert unarchive.status_code == 200
    assert unarchive.json()["status"] == "active"

    thumbnail = client.get(f"/api/projects/{project_id}/thumbnail")
    assert thumbnail.status_code == 200
    assert b"Renamed API Box" in thumbnail.content

    delete = client.request("DELETE", f"/api/projects/{duplicate_id}", json={"confirmation": "DELETE"})
    assert delete.status_code == 200
    assert store.get_project(duplicate_id) is None


def test_assembly_lifecycle_store_and_api(tmp_path) -> None:
    projects, project_id = make_project(tmp_path, name="Assembly Source")
    assemblies = assembly_store(tmp_path)
    assembly = create_assembly(name="Workflow Assembly", store=assemblies)
    initialize_revision(
        assembly_id=assembly.assembly_id,
        components=[
            AssemblyComponent(
                component_id="source",
                name="Source",
                source_type=ComponentSourceType.PROJECT_REVISION,
                project_id=project_id,
                project_revision=1,
            )
        ],
        store=assemblies,
        project_store=projects,
    )

    app = create_app()
    app.dependency_overrides[get_project_store] = lambda: projects
    app.dependency_overrides[get_assembly_store] = lambda: assemblies
    client = TestClient(app)

    assert client.patch(f"/api/assemblies/{assembly.assembly_id}", json={"name": "Renamed Assembly"}).json()["name"] == "Renamed Assembly"
    detail = client.get(f"/api/assemblies/{assembly.assembly_id}")
    assert detail.status_code == 200
    assert assemblies.get_assembly(assembly.assembly_id).last_opened_at is not None

    duplicate = client.post(f"/api/assemblies/{assembly.assembly_id}/duplicate", json={})
    assert duplicate.status_code == 200
    duplicate_id = duplicate.json()["assembly"]["assembly_id"]
    assert duplicate_id != assembly.assembly_id

    assert client.post(f"/api/assemblies/{assembly.assembly_id}/archive").json()["status"] == "archived"
    active = client.get("/api/assemblies", params={"status": "active"})
    assert all(item["assembly_id"] != assembly.assembly_id for item in active.json())
    assert client.post(f"/api/assemblies/{assembly.assembly_id}/unarchive").json()["status"] == "active"

    thumbnail = client.get(f"/api/assemblies/{assembly.assembly_id}/thumbnail")
    assert thumbnail.status_code == 200
    assert b"Renamed Assembly" in thumbnail.content

    delete = client.request("DELETE", f"/api/assemblies/{duplicate_id}", json={"confirmation": "DELETE"})
    assert delete.status_code == 200
    assert assemblies.get_assembly(duplicate_id) is None
