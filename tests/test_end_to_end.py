"""Deterministic end-to-end workflow.

Exercises the real integration path across projects, revisions, engineering,
exports, and assemblies, using isolated temporary databases and no AI. This is
the test that catches a break between subsystems that per-module tests each
pass individually.
"""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from ai.schemas import HoleSpec, MountingPlateSpec
from assemblies.manager import assembly_engineering, assembly_preview, initialize_revision
from assemblies.models import AssemblyComponent, ComponentSourceType, Transform
from assemblies.store import AssemblyStore
from cad.generator import generate_step
from engineering.analyzer import analyze_part
from exports.store import ExportStore
from learning.store import LearningStore
from projects.manager import create_project_from_model
from projects.revisions import redo, undo
from projects.serialization import model_from_json, model_to_json, model_type_for
from projects.store import ProjectStore


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A fresh installation: empty directories and brand-new databases."""
    data_dir = tmp_path / "data"
    outputs_dir = tmp_path / "outputs"
    data_dir.mkdir()
    outputs_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    return {
        "root": tmp_path,
        "data": data_dir,
        "projects": ProjectStore(data_dir / "projects.db"),
        "assemblies": AssemblyStore(data_dir / "assemblies.db"),
        "exports": ExportStore(data_dir / "exports.db"),
        "learning": LearningStore(data_dir / "learning.db"),
        "outputs": outputs_dir,
    }


def _plate(width: float = 100.0, hole_diameter: float = 5.0) -> MountingPlateSpec:
    offset_x = width / 2 - 8
    return MountingPlateSpec(
        width_mm=width,
        height_mm=60.0,
        thickness_mm=5.0,
        corner_radius_mm=2.0,
        holes=[
            HoleSpec(diameter_mm=hole_diameter, x_mm=x, y_mm=y)
            for x in (-offset_x, offset_x)
            for y in (-22.0, 22.0)
        ],
    )


def _create_part(workspace, name: str, model: MountingPlateSpec):
    """Create a project and write its STEP, as the API flow does."""
    project, revision = create_project_from_model(
        name=name,
        model=model,
        source_prompt=f"deterministic fixture for {name}",
        store=workspace["projects"],
    )
    step_path = workspace["outputs"] / f"{project.project_id}.step"
    generate_step(model, step_path)
    return project, revision, step_path


# ---------------------------------------------------------------------------
# Fresh start
# ---------------------------------------------------------------------------


def test_fresh_start_creates_all_databases(workspace):
    """A brand-new installation initializes every store with a usable schema."""
    for name in ("projects.db", "assemblies.db", "exports.db", "learning.db"):
        path = workspace["data"] / name
        assert path.is_file(), f"{name} was not created"
        with sqlite3.connect(path) as conn:
            tables = {
                row[0]
                for row in conn.execute("select name from sqlite_master where type='table'")
            }
        assert tables, f"{name} has no tables"


def test_fresh_start_has_no_projects(workspace):
    assert workspace["projects"].list_projects() == []
    assert workspace["assemblies"].list_assemblies() == []


# ---------------------------------------------------------------------------
# Part workflow
# ---------------------------------------------------------------------------


def test_end_to_end_part_workflow(workspace):
    """Create, generate, revise, undo, redo, and export a part."""
    store: ProjectStore = workspace["projects"]
    project, revision, step_path = _create_part(workspace, "E2E Plate", _plate())

    assert revision.revision_number == 1
    assert step_path.read_bytes().startswith(b"ISO-10303-21;")

    # Edit a dimension, creating a second revision.
    wider = _plate(width=120.0)
    wider_path = workspace["outputs"] / "plate_rev2.step"
    generate_step(wider, wider_path)
    store.add_revision(
        project_id=project.project_id,
        parent_revision_id=revision.revision_id,
        user_instruction="Make the plate 120 mm wide",
        model_type=model_type_for(wider),
        structured_spec_json=model_to_json(wider),
        change_summary="plate width 100 -> 120 mm",
        step_output_path=str(wider_path),
    )
    assert len(store.history(project.project_id)) == 2
    assert store.get_project(project.project_id).current_revision == 2

    # The stored spec round-trips and reflects the edit.
    current = store.current_revision(project.project_id)
    restored = model_from_json(current.model_type, current.structured_spec_json)
    assert isinstance(restored, MountingPlateSpec)
    assert restored.width_mm == 120.0

    # Undo returns to revision 1, redo returns to 2.
    assert undo(store=store, project_id=project.project_id).revision_number == 1
    assert redo(store=store, project_id=project.project_id).revision_number == 2

    # Export and verify the artifact really exists on disk.
    export_path = workspace["outputs"] / "final.step"
    generate_step(restored, export_path)
    assert export_path.stat().st_size > 1000


def test_end_to_end_engineering_report(workspace):
    """Engineering analysis produces a mass consistent with the material."""
    report = analyze_part(
        _plate(), material_id="aluminum_6061", manufacturing_process="cnc_machining"
    )
    assert report.mass_estimate is not None
    # 100 x 60 x 5 mm is 30 cm3 before holes; aluminium is 2.7 g/cm3, so the
    # plate must be under the solid-block mass and well above zero.
    assert 0 < report.mass_estimate.mass_g < 81


def test_end_to_end_material_change_updates_mass(workspace):
    """A denser material must report a greater mass for the same geometry."""
    model = _plate()
    aluminium = analyze_part(model, material_id="aluminum_6061")
    steel = analyze_part(model, material_id="mild_steel")
    assert aluminium.mass_estimate is not None
    assert steel.mass_estimate is not None
    assert steel.mass_estimate.mass_g > aluminium.mass_estimate.mass_g


def test_end_to_end_material_assignment_persists(workspace):
    store: ProjectStore = workspace["projects"]
    project, _, _ = _create_part(workspace, "Material Part", _plate())
    store.set_material_assignment(project.project_id, "aluminum_6061")
    assert store.get_material_assignment(project.project_id) == "aluminum_6061"


# ---------------------------------------------------------------------------
# Assembly workflow
# ---------------------------------------------------------------------------


def test_end_to_end_assembly_workflow(workspace):
    """Build an assembly from two real projects and check it holds together."""
    projects: ProjectStore = workspace["projects"]
    assemblies: AssemblyStore = workspace["assemblies"]

    components: list[AssemblyComponent] = []
    for index, width in enumerate((60.0, 40.0), start=1):
        project, _, _ = _create_part(workspace, f"Component {index}", _plate(width=width))
        components.append(
            AssemblyComponent(
                component_id=f"component_{index}",
                name=f"Component {index}",
                source_type=ComponentSourceType.PROJECT_REVISION,
                project_id=project.project_id,
                project_revision=1,
                transform=Transform(translation_z_mm=index * 40.0),
                grounded=index == 1,
            )
        )

    record = assemblies.create_assembly(name="E2E Assembly", notes=None)
    initialize_revision(
        assembly_id=record.assembly_id,
        components=components,
        store=assemblies,
        project_store=projects,
    )

    preview = assembly_preview(
        assembly_id=record.assembly_id, store=assemblies, project_store=projects
    )
    assert len(preview.components) == 2

    summary = assembly_engineering(
        assembly_id=record.assembly_id, store=assemblies, project_store=projects
    )
    # Two vertically separated components must not be reported as interfering.
    assert summary.interferences == []


def test_end_to_end_assembly_detects_overlap(workspace):
    """Two components in the same space must be reported as interfering."""
    projects: ProjectStore = workspace["projects"]
    assemblies: AssemblyStore = workspace["assemblies"]

    components: list[AssemblyComponent] = []
    for index in (1, 2):
        project, _, _ = _create_part(workspace, f"Stacked {index}", _plate(width=60.0))
        components.append(
            AssemblyComponent(
                component_id=f"stacked_{index}",
                name=f"Stacked {index}",
                source_type=ComponentSourceType.PROJECT_REVISION,
                project_id=project.project_id,
                project_revision=1,
                # Deliberately overlapping: both occupy the same volume.
                transform=Transform(translation_z_mm=float(index)),
                grounded=index == 1,
            )
        )

    record = assemblies.create_assembly(name="Overlapping", notes=None)
    initialize_revision(
        assembly_id=record.assembly_id,
        components=components,
        store=assemblies,
        project_store=projects,
    )
    summary = assembly_engineering(
        assembly_id=record.assembly_id, store=assemblies, project_store=projects
    )
    assert summary.interferences, "overlapping components should be reported"


# ---------------------------------------------------------------------------
# Project management
# ---------------------------------------------------------------------------


def test_end_to_end_duplicate_and_archive(workspace):
    """Duplicate keeps the original intact; archive is reversible."""
    store: ProjectStore = workspace["projects"]
    project, _, _ = _create_part(workspace, "Original", _plate())

    copy, _ = store.duplicate_project(project.project_id, name="Copy")
    assert copy.project_id != project.project_id
    assert copy.name == "Copy"
    assert store.get_project(project.project_id).name == "Original"

    store.archive_project(copy.project_id)
    active_ids = {item.project_id for item in store.list_projects(status="active")}
    assert copy.project_id not in active_ids
    assert project.project_id in active_ids

    store.unarchive_project(copy.project_id)
    assert copy.project_id in {item.project_id for item in store.list_projects(status="active")}


def test_end_to_end_search_finds_project(workspace):
    store: ProjectStore = workspace["projects"]
    _create_part(workspace, "Searchable Bracket", _plate())
    assert [item.name for item in store.list_projects(search="Bracket")] == ["Searchable Bracket"]
    assert store.list_projects(search="no-such-project") == []


def test_end_to_end_rename_project(workspace):
    store: ProjectStore = workspace["projects"]
    project, _, _ = _create_part(workspace, "Before", _plate())
    store.rename_project(project.project_id, "After")
    assert store.get_project(project.project_id).name == "After"


# ---------------------------------------------------------------------------
# Upgrade safety
# ---------------------------------------------------------------------------


def test_opening_an_existing_database_preserves_data(workspace):
    """Re-opening a populated database must not recreate or wipe it."""
    project, _, _ = _create_part(workspace, "Persistent", _plate())

    # A second store over the same file is what a restart looks like.
    reopened = ProjectStore(workspace["data"] / "projects.db")
    assert [item.name for item in reopened.list_projects()] == ["Persistent"]
    assert reopened.get_project(project.project_id).current_revision == 1


# ---------------------------------------------------------------------------
# Backup contents
# ---------------------------------------------------------------------------


def test_backup_archives_databases_without_secrets(tmp_path, monkeypatch):
    """The archive must carry the databases and no secret or bulk directory."""
    from deployment import launcher, paths

    root = tmp_path
    data = root / "data"
    data.mkdir()
    databases = []
    for name in ("shah_learning.db", "shah_projects.db"):
        path = data / name
        path.write_bytes(b"SQLite format 3\x00")
        databases.append(path)

    secret = root / ".env"
    secret.write_text("OPENAI_API_KEY=must-not-be-archived", encoding="utf-8")
    node_modules = root / "web" / "node_modules"
    node_modules.mkdir(parents=True)
    (node_modules / "big.js").write_text("x" * 100, encoding="utf-8")
    logs = root / "runtime" / "logs"
    logs.mkdir(parents=True)
    (logs / "backend.log").write_text("log line", encoding="utf-8")

    monkeypatch.setattr(paths, "REPO_ROOT", root)
    monkeypatch.setattr(launcher.paths, "REPO_ROOT", root)
    monkeypatch.setattr(launcher.paths, "BACKUPS_DIR", root / "backups")
    monkeypatch.setattr(launcher.paths, "DATA_DIR", data)
    monkeypatch.setattr(launcher.paths, "DATABASE_FILES", tuple(databases))
    monkeypatch.setattr(launcher.paths, "MCP_CONFIG_PATH", root / "absent.json")
    monkeypatch.setattr(launcher.paths, "LOCAL_CONFIG_PATH", root / "absent-local.json")
    monkeypatch.setattr(launcher.paths, "ENV_PATH", secret)

    assert launcher.backup() == 0

    archives = list((root / "backups").glob("shah_backup_*.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as archive:
        names = archive.namelist()

    assert any("shah_projects.db" in name for name in names)
    assert any("shah_learning.db" in name for name in names)
    for forbidden in (".env", "node_modules", ".venv", "runtime/logs", "backend.log"):
        assert not any(forbidden in name for name in names), forbidden


# ---------------------------------------------------------------------------
# Benchmark corpus integrity
# ---------------------------------------------------------------------------


def test_benchmark_corpus_is_loadable_and_covers_categories():
    from collections import Counter

    from evaluation.fixtures import load_cases

    full = load_cases()
    smoke = load_cases(smoke=True)

    assert len(full) >= 60, "the deterministic corpus should cover at least 60 cases"
    # Smoke stays small enough to run on every change.
    assert 20 <= len(smoke) <= 35, f"smoke suite is {len(smoke)} cases"

    categories = Counter(case.category for case in full)
    assert len(categories) >= 15, f"only {len(categories)} categories covered"

    missing = set(categories) - {case.category for case in smoke}
    assert not missing, f"smoke suite misses categories: {sorted(missing)}"


def test_benchmark_case_ids_are_unique():
    from evaluation.fixtures import load_cases

    ids = [case.case_id for case in load_cases()]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    assert not duplicates, f"duplicate case ids: {duplicates}"


def test_benchmark_baseline_matches_corpus():
    """The committed baseline must cover the cases the suite will run."""
    baseline = json.loads(Path("benchmarks/baselines/current.json").read_text(encoding="utf-8"))
    from evaluation.fixtures import load_cases

    baseline_ids = {result["case_id"] for result in baseline["results"]}
    missing = {case.case_id for case in load_cases()} - baseline_ids
    assert not missing, f"cases absent from the baseline: {sorted(missing)}"


def test_benchmark_includes_expected_failure_cases():
    """The corpus must cover clean refusals, not just happy paths."""
    from evaluation.models import BenchmarkStatus
    from evaluation.fixtures import load_cases

    cases = load_cases()
    unsupported = [c for c in cases if c.expected_status is BenchmarkStatus.UNSUPPORTED]
    failures = [c for c in cases if c.expected_failure_category is not None]
    assert len(unsupported) >= 3, "expected several cleanly unsupported requests"
    assert len(failures) >= 8, "expected a body of clean-failure cases"
