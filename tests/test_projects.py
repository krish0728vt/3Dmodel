from __future__ import annotations

import pytest

import app
from ai.schemas import (
    BooleanUnionOperation,
    BoxSpec,
    CreateBoxOperation,
    CreateCylinderOperation,
    CutHoleOperation,
    FilletOperation,
    OperationPlan,
)
from learning.store import LearningStore
from projects.diff import diff_models, diff_revisions
from projects.editor import EditApplicationError, apply_edit, apply_edit_to_project
from projects.manager import create_project_from_model
from projects.models import (
    AddOperationEdit,
    ModifyOperationEdit,
    RemoveOperationEdit,
    SetParameterEdit,
)
from projects.revisions import export_revision, redo, restore, undo
from projects.store import ProjectStore


def boss_plan() -> OperationPlan:
    return OperationPlan(
        project_name="motor_mount",
        operations=[
            CreateBoxOperation(
                id="base",
                label="base plate",
                width_mm=80,
                depth_mm=50,
                height_mm=5,
                center=(0, 0, 2.5),
            ),
            CreateCylinderOperation(
                id="center_boss",
                label="center boss",
                diameter_mm=20,
                height_mm=15,
                center=(0, 0, 12.5),
            ),
            BooleanUnionOperation(id="combined", target_id="base", tool_id="center_boss"),
        ],
        final_object_id="combined",
    )


def project_store(tmp_path) -> ProjectStore:
    return ProjectStore(tmp_path / "projects.db")


def learning_store(tmp_path) -> LearningStore:
    return LearningStore(tmp_path / "learning.db")


def test_project_store_create_initial_revision_and_history(tmp_path) -> None:
    store = project_store(tmp_path)
    project, revision = create_project_from_model(
        name="Box Project",
        model=BoxSpec(width_mm=10, depth_mm=20, height_mm=5),
        source_prompt="box",
        store=store,
    )

    assert project.project_id.startswith("proj_")
    assert revision.revision_number == 1
    assert store.current_revision(project.project_id).revision_number == 1
    assert [rev.revision_number for rev in store.history(project.project_id)] == [1]


def test_template_edit_width_and_thickness_old_revision_unchanged(tmp_path) -> None:
    store = project_store(tmp_path)
    project, rev1 = create_project_from_model(
        name="Editable Box",
        model=BoxSpec(width_mm=10, depth_mm=20, height_mm=5),
        source_prompt=None,
        store=store,
    )

    rev2, summary = apply_edit_to_project(
        project_id=project.project_id,
        edit=SetParameterEdit(path="width_mm", value=15),
        user_instruction="make it wider",
        store=store,
        learning_store=learning_store(tmp_path),
    )

    assert rev2.revision_number == 2
    assert "width_mm" in summary
    assert '"width_mm":10.0' in rev1.structured_spec_json
    assert store.current_revision(project.project_id).revision_number == 2


def test_invalid_template_edit_rejected_and_active_revision_unchanged(tmp_path) -> None:
    store = project_store(tmp_path)
    learning = learning_store(tmp_path)
    project, _ = create_project_from_model(
        name="Safe Box",
        model=BoxSpec(width_mm=10, depth_mm=20, height_mm=5),
        source_prompt=None,
        store=store,
    )

    with pytest.raises(Exception):
        apply_edit_to_project(
            project_id=project.project_id,
            edit=SetParameterEdit(path="width_mm", value=-1),
            user_instruction="make it invalid",
            store=store,
            learning_store=learning,
        )

    assert store.current_revision(project.project_id).revision_number == 1
    assert learning.stats()["failures"] == 1


def test_operation_modify_add_remove_and_fillet_edits(tmp_path) -> None:
    plan = boss_plan()
    taller, summary = apply_edit(
        plan,
        ModifyOperationEdit(operation_id="center_boss", changes={"height_mm": 20, "center": (0, 0, 15)}),
    )
    assert "center_boss" in summary
    assert taller.operations[1].height_mm == 20

    holed, summary = apply_edit(
        OperationPlan(project_name="holed", operations=plan.operations, final_object_id=None),
        AddOperationEdit(
            operation=CutHoleOperation(
                id="center_hole",
                target_id="combined",
                diameter_mm=6,
                position=(0, 0),
                direction="z",
            )
        ),
    )
    assert holed.operations[-1].id == "center_hole"
    assert holed.final_object_id == "center_hole"
    assert "Added operation" in summary

    unholed, summary = apply_edit(holed, RemoveOperationEdit(operation_id="center_hole"))
    assert all(operation.id != "center_hole" for operation in unholed.operations)
    assert "Removed operation" in summary

    filleted, summary = apply_edit(
        OperationPlan(
            project_name="fillet_plan",
            operations=[CreateBoxOperation(id="base", width_mm=20, depth_mm=20, height_mm=5)],
        ),
        AddOperationEdit(
            operation=FilletOperation(
                id="soften",
                target_id="base",
                radius_mm=1,
                edge_selector="vertical_edges",
            )
        ),
    )
    assert filleted.operations[-1].operation_type == "fillet"


def test_invalid_operation_id_rejected() -> None:
    with pytest.raises(EditApplicationError, match="Unknown operation id"):
        apply_edit(
            boss_plan(),
            ModifyOperationEdit(operation_id="missing", changes={"height_mm": 20}),
        )


def test_undo_redo_restore_and_branch_after_undo(tmp_path) -> None:
    store = project_store(tmp_path)
    project, _ = create_project_from_model(
        name="Branching Box",
        model=BoxSpec(width_mm=10, depth_mm=20, height_mm=5),
        source_prompt=None,
        store=store,
    )
    apply_edit_to_project(
        project_id=project.project_id,
        edit=SetParameterEdit(path="width_mm", value=15),
        user_instruction="wider",
        store=store,
        learning_store=learning_store(tmp_path),
    )
    apply_edit_to_project(
        project_id=project.project_id,
        edit=SetParameterEdit(path="height_mm", value=8),
        user_instruction="taller",
        store=store,
        learning_store=learning_store(tmp_path),
    )

    assert undo(project.project_id, store=store).revision_number == 2
    assert redo(project.project_id, store=store).revision_number == 3
    assert restore(project.project_id, 1, store=store).revision_number == 1
    restore(project.project_id, 2, store=store)
    rev4, _ = apply_edit_to_project(
        project_id=project.project_id,
        edit=SetParameterEdit(path="depth_mm", value=25),
        user_instruction="deeper branch",
        store=store,
        learning_store=learning_store(tmp_path),
    )

    assert rev4.revision_number == 4
    assert rev4.parent_revision_id == store.get_revision(project.project_id, 2).revision_id
    assert [rev.revision_number for rev in store.history(project.project_id)] == [1, 2, 3, 4]


def test_diff_parameter_and_operation_changes(tmp_path) -> None:
    assert "width_mm" in diff_models(
        BoxSpec(width_mm=10, depth_mm=20, height_mm=5),
        BoxSpec(width_mm=15, depth_mm=20, height_mm=5),
    )
    assert "Added operation" in diff_models(
        boss_plan(),
        OperationPlan(
            project_name="with_hole",
            operations=[
                *boss_plan().operations,
                CutHoleOperation(id="hole", target_id="combined", diameter_mm=6),
            ],
        ),
    )

    store = project_store(tmp_path)
    project, _ = create_project_from_model(
        name="Diff Box",
        model=BoxSpec(width_mm=10, depth_mm=20, height_mm=5),
        source_prompt=None,
        store=store,
    )
    apply_edit_to_project(
        project_id=project.project_id,
        edit=SetParameterEdit(path="width_mm", value=15),
        user_instruction="wider",
        store=store,
        learning_store=learning_store(tmp_path),
    )
    assert "width_mm" in diff_revisions(project.project_id, 1, 2, store=store)


def test_export_current_and_older_revision(tmp_path) -> None:
    store = project_store(tmp_path)
    project, _ = create_project_from_model(
        name="Export Box",
        model=BoxSpec(width_mm=10, depth_mm=20, height_mm=5),
        source_prompt=None,
        store=store,
    )
    apply_edit_to_project(
        project_id=project.project_id,
        edit=SetParameterEdit(path="width_mm", value=15),
        user_instruction="wider",
        store=store,
        learning_store=learning_store(tmp_path),
    )

    current = export_revision(project.project_id, store=store)
    old = export_revision(project.project_id, 1, store=store)

    assert current.exists()
    assert current.stat().st_size > 0
    assert old.exists()
    assert old.stat().st_size > 0


def test_project_cli_history_restore_diff_and_export(monkeypatch, tmp_path, capsys) -> None:
    store = project_store(tmp_path)
    project, _ = create_project_from_model(
        name="CLI Box",
        model=BoxSpec(width_mm=10, depth_mm=20, height_mm=5),
        source_prompt=None,
        store=store,
    )
    apply_edit_to_project(
        project_id=project.project_id,
        edit=SetParameterEdit(path="width_mm", value=15),
        user_instruction="wider",
        store=store,
        learning_store=learning_store(tmp_path),
    )
    monkeypatch.setattr(app, "ProjectStore", lambda: store)

    assert app.main(["project", "list"]) == 0
    assert project.project_id in capsys.readouterr().out
    assert app.main(["project", "history", project.project_id]) == 0
    assert "rev 2" in capsys.readouterr().out
    assert app.main(["project", "diff", project.project_id, "1", "2"]) == 0
    assert "width_mm" in capsys.readouterr().out
    assert app.main(["project", "restore", project.project_id, "1"]) == 0
    assert "Restored revision: 1" in capsys.readouterr().out
    assert app.main(["project", "export", project.project_id, "--revision", "2"]) == 0
    assert "Exported:" in capsys.readouterr().out
