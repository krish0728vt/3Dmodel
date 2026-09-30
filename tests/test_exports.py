from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai.schemas import (
    BoxSpec,
    CreateBoxOperation,
    CreateSketchOperation,
    ExtrudeOperation,
    OperationPlan,
    RectangleEntity,
    SketchPlan,
    SlotEntity,
    CircleEntity,
)
from api.dependencies import get_assembly_store, get_export_store, get_project_store
from api.server import create_app
from assemblies.manager import create_assembly, initialize_revision
from assemblies.models import AssemblyComponent, ComponentSourceType, Transform
from assemblies.store import AssemblyStore
from capabilities.adapters.spur_gear import invoke as invoke_spur_gear
from exports.dxf import export_plan_sketch_dxf
from exports.manager import ExportError, checksum_file, run_export
from exports.models import ExportFormat, ExportOptions, ExportRequest, ExportSourceType, StlQuality
from exports.naming import UnsafeExportPathError, ensure_controlled_path
from exports.store import ExportStore
from projects.manager import create_project_from_model
from projects.store import ProjectStore


def project_store(tmp_path) -> ProjectStore:
    return ProjectStore(tmp_path / "projects.db")


def assembly_store(tmp_path) -> AssemblyStore:
    return AssemblyStore(tmp_path / "assemblies.db")


def export_store(tmp_path) -> ExportStore:
    return ExportStore(tmp_path / "exports.db")


def make_project(tmp_path, model=None) -> tuple[ProjectStore, str]:
    store = project_store(tmp_path)
    project, _ = create_project_from_model(
        name="Export Box",
        model=model or BoxSpec(width_mm=20, depth_mm=12, height_mm=6),
        source_prompt="export test",
        store=store,
    )
    return store, project.project_id


def sketch_plan() -> OperationPlan:
    return OperationPlan(
        project_name="laser_plate",
        operations=[
            CreateSketchOperation(
                id="profile",
                sketch=SketchPlan(
                    id="profile",
                    plane="XY",
                    entities=[
                        RectangleEntity(width_mm=40, height_mm=20),
                    ],
                ),
            ),
            ExtrudeOperation(id="solid", sketch_id="profile", distance_mm=3),
        ],
        final_object_id="solid",
    )


def test_step_round_trip_manifest_zip_and_history(tmp_path) -> None:
    projects, project_id = make_project(tmp_path)
    exports = export_store(tmp_path)

    batch = run_export(
        ExportRequest(
            source_type=ExportSourceType.PROJECT_REVISION,
            source_id=project_id,
            revision=1,
            formats=[ExportFormat.STEP, ExportFormat.STL],
            options=ExportOptions(stl_quality=StlQuality.STANDARD, package=True),
        ),
        project_store=projects,
        export_store=exports,
    )

    formats = {result.format for result in batch.results}
    assert {ExportFormat.STEP, ExportFormat.STL, ExportFormat.MANIFEST, ExportFormat.ZIP}.issubset(formats)
    step = next(result for result in batch.results if result.format == ExportFormat.STEP)
    manifest = next(result for result in batch.results if result.format == ExportFormat.MANIFEST)
    package = next(result for result in batch.results if result.format == ExportFormat.ZIP)
    assert step.metadata["round_trip"]["round_trip_volume_mm3"] == pytest.approx(step.metadata["round_trip"]["original_volume_mm3"], rel=0.02)
    assert step.filename == "Export_Box_rev_001.step"
    assert checksum_file(Path(step.path)) == step.checksum_sha256

    manifest_data = json.loads(Path(manifest.path).read_text(encoding="utf-8"))
    assert manifest_data["source"]["revision"] == 1
    assert any(item["format"] == "step" for item in manifest_data["formats"])
    assert manifest_data["engineering"]["volume_mm3"] > 0

    with zipfile.ZipFile(package.path) as archive:
        names = set(archive.namelist())
    assert step.filename in names
    assert manifest.filename in names

    history = exports.list_for_source(ExportSourceType.PROJECT_REVISION, project_id)
    assert {record.format for record in history}.issuperset({ExportFormat.STEP, ExportFormat.STL, ExportFormat.MANIFEST, ExportFormat.ZIP})


def test_stl_quality_presets_return_mesh_metadata(tmp_path) -> None:
    projects, project_id = make_project(tmp_path)
    exports = export_store(tmp_path)

    draft = run_export(
        ExportRequest(
            source_type=ExportSourceType.PROJECT_REVISION,
            source_id=project_id,
            revision=1,
            formats=[ExportFormat.STL],
            options=ExportOptions(stl_quality=StlQuality.DRAFT, include_manifest=False),
        ),
        project_store=projects,
        export_store=exports,
    ).results[0]
    high = run_export(
        ExportRequest(
            source_type=ExportSourceType.PROJECT_REVISION,
            source_id=project_id,
            revision=1,
            formats=[ExportFormat.STL],
            options=ExportOptions(stl_quality=StlQuality.HIGH, include_manifest=False),
        ),
        project_store=projects,
        export_store=exports,
    ).results[0]

    assert draft.metadata["quality"] == "draft"
    assert high.metadata["quality"] == "high"
    assert draft.metadata["triangle_count"] is not None
    assert high.metadata["triangle_count"] >= draft.metadata["triangle_count"]
    assert high.size_bytes >= draft.size_bytes


def test_dxf_export_for_structured_sketches_and_rejects_3d_only(tmp_path) -> None:
    plan = sketch_plan()
    dxf_path = export_plan_sketch_dxf(
        OperationPlan(
            project_name="direct_dxf",
            operations=[
                CreateSketchOperation(
                    id="profile",
                    sketch=SketchPlan(
                        id="profile",
                        entities=[
                            RectangleEntity(width_mm=10, height_mm=5),
                            CircleEntity(center=(2, 0), diameter_mm=3),
                            SlotEntity(center=(0, 4), length_mm=12, width_mm=3),
                        ],
                    ),
                ),
                ExtrudeOperation(id="solid", sketch_id="profile", distance_mm=1),
            ],
            final_object_id="solid",
        ),
        tmp_path / "profile.dxf",
    )
    text = dxf_path.read_text(encoding="ascii")
    assert "LWPOLYLINE" in text
    assert "CIRCLE" in text
    assert "OUTLINE" in text
    assert "HOLES" in text

    projects, project_id = make_project(tmp_path, plan)
    batch = run_export(
        ExportRequest(
            source_type=ExportSourceType.PROJECT_REVISION,
            source_id=project_id,
            revision=1,
            formats=[ExportFormat.DXF],
            options=ExportOptions(include_manifest=False),
        ),
        project_store=projects,
        export_store=export_store(tmp_path),
    )
    assert batch.results[0].filename.endswith(".dxf")

    solid_projects, solid_project_id = make_project(tmp_path / "solid")
    with pytest.raises(ExportError, match="structured 2D sketch"):
        run_export(
            ExportRequest(
                source_type=ExportSourceType.PROJECT_REVISION,
                source_id=solid_project_id,
                revision=1,
                formats=[ExportFormat.DXF],
            ),
            project_store=solid_projects,
            export_store=export_store(tmp_path / "solid"),
        )


def test_assembly_step_stl_manifest_exports(tmp_path) -> None:
    projects, project_id = make_project(tmp_path)
    assemblies = assembly_store(tmp_path)
    assembly = create_assembly(name="Gearbox Assembly", store=assemblies)
    initialize_revision(
        assembly_id=assembly.assembly_id,
        components=[
            AssemblyComponent(
                component_id="base",
                name="Base",
                source_type=ComponentSourceType.PROJECT_REVISION,
                project_id=project_id,
                project_revision=1,
                transform=Transform(),
            ),
            AssemblyComponent(
                component_id="cover",
                name="Cover",
                source_type=ComponentSourceType.PROJECT_REVISION,
                project_id=project_id,
                project_revision=1,
                transform=Transform(translation_x_mm=25),
            ),
        ],
        store=assemblies,
        project_store=projects,
    )

    batch = run_export(
        ExportRequest(
            source_type=ExportSourceType.ASSEMBLY_REVISION,
            source_id=assembly.assembly_id,
            revision=1,
            formats=[ExportFormat.STEP, ExportFormat.STL],
        ),
        project_store=projects,
        assembly_store=assemblies,
        export_store=export_store(tmp_path),
    )

    assert {result.format for result in batch.results}.issuperset({ExportFormat.STEP, ExportFormat.STL, ExportFormat.MANIFEST})
    manifest = next(result for result in batch.results if result.format == ExportFormat.MANIFEST)
    data = json.loads(Path(manifest.path).read_text(encoding="utf-8"))
    assert data["assembly"]["components"][1]["transform"]["translation_x_mm"] == 25


def test_export_api_batch_download_history_and_invalid_requests(tmp_path) -> None:
    projects, project_id = make_project(tmp_path, sketch_plan())
    assemblies = assembly_store(tmp_path)
    exports = export_store(tmp_path)
    app = create_app()
    app.dependency_overrides[get_project_store] = lambda: projects
    app.dependency_overrides[get_assembly_store] = lambda: assemblies
    app.dependency_overrides[get_export_store] = lambda: exports
    client = TestClient(app)

    response = client.post(
        "/api/exports",
        json={
            "source_type": "project_revision",
            "source_id": project_id,
            "revision": 1,
            "formats": ["step", "stl", "dxf"],
            "options": {"stl_quality": "high", "package": True},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 1
    assert {item["format"] for item in body["results"]}.issuperset({"step", "stl", "dxf", "manifest", "zip"})

    step = next(item for item in body["results"] if item["format"] == "step")
    detail = client.get(f"/api/exports/{step['export_id']}")
    assert detail.status_code == 200
    download = client.get(f"/api/exports/{step['export_id']}/download")
    assert download.status_code == 200
    assert len(download.content) > 0

    history = client.get(f"/api/projects/{project_id}/exports")
    assert history.status_code == 200
    assert len(history.json()) >= 4

    invalid_format = client.post(
        "/api/exports",
        json={"source_type": "project_revision", "source_id": project_id, "revision": 1, "formats": ["bad"]},
    )
    assert invalid_format.status_code == 422

    invalid_revision = client.post(
        "/api/exports",
        json={"source_type": "project_revision", "source_id": project_id, "revision": 99, "formats": ["step"]},
    )
    assert invalid_revision.status_code == 400


def test_path_safety_rejects_traversal() -> None:
    with pytest.raises(UnsafeExportPathError):
        ensure_controlled_path(Path("outputs") / ".." / "escape.step")


def test_capability_output_step_and_stl_export(tmp_path) -> None:
    result = invoke_spur_gear({"module_mm": 1, "teeth": 18, "thickness_mm": 4, "bore_diameter_mm": 4})
    step_path = result.step_path
    stl_path = result.stl_path

    step_batch = run_export(
        ExportRequest(
            source_type=ExportSourceType.CAPABILITY_OUTPUT,
            source_id=step_path,
            formats=[ExportFormat.STEP, ExportFormat.STL],
            options=ExportOptions(include_manifest=False),
        ),
        export_store=export_store(tmp_path),
    )
    assert {item.format for item in step_batch.results} == {ExportFormat.STEP, ExportFormat.STL}

    stl_batch = run_export(
        ExportRequest(
            source_type=ExportSourceType.CAPABILITY_OUTPUT,
            source_id=stl_path,
            formats=[ExportFormat.STL],
            options=ExportOptions(include_manifest=False),
        ),
        export_store=export_store(tmp_path),
    )
    assert stl_batch.results[0].filename.endswith(".stl")
