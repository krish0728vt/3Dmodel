from __future__ import annotations

import pytest

from ai.schemas import (
    BlindHoleOperation,
    BossOperation,
    CircleEntity,
    CircularHolePatternOperation,
    CounterboreHoleOperation,
    CountersinkHoleOperation,
    CreateBoxOperation,
    CreateSketchOperation,
    CutExtrudeOperation,
    LineEntity,
    LoftOperation,
    OperationPlan,
    PolygonEntity,
    PolylineEntity,
    RectangleEntity,
    RectangularHolePatternOperation,
    RibOperation,
    ShellOperation,
    SketchPlan,
    SlotEntity,
    SweepOperation,
    ThroughHoleOperation,
)
from cad.generator import generate_step, generate_stl
from cad.operation_executor import OperationExecutionError, execute_operation_plan
from cad.operation_validator import OperationValidationError, validate_operation_plan
from learning.classifier import classify_failure
from learning.models import FailureCategory
from projects.editor import apply_edit
from projects.models import ModifyOperationEdit


def sketch_operation(sketch: SketchPlan) -> CreateSketchOperation:
    return CreateSketchOperation(id=sketch.id, label=sketch.label, sketch=sketch)


@pytest.mark.parametrize(
    "entity",
    [
        LineEntity(start=(0, 0), end=(10, 0)),
        PolylineEntity(points=[(0, 0), (10, 0), (10, 5)], closed=False),
        RectangleEntity(width_mm=10, height_mm=5),
        CircleEntity(diameter_mm=10),
        PolygonEntity(radius_mm=8, sides=6),
        SlotEntity(length_mm=24, width_mm=8),
    ],
)
def test_sketch_entities_validate(entity) -> None:
    sketch = SketchPlan(id="sketch", entities=[entity], closed=entity.entity_type not in {"line", "polyline"})
    if sketch.closed:
        plan = OperationPlan(
            project_name="sketch_entity",
            operations=[
                sketch_operation(sketch),
                {"id": "solid", "operation_type": "extrude", "sketch_id": "sketch", "distance_mm": 2},
            ],
        )
    else:
        plan = OperationPlan(
            project_name="sketch_entity",
            operations=[
                sketch_operation(SketchPlan(id="profile", plane="YZ", entities=[CircleEntity(diameter_mm=2)])),
                sketch_operation(sketch),
                SweepOperation(id="solid", profile_sketch_id="profile", path_sketch_id="sketch"),
            ],
        )

    validate_operation_plan(plan)


@pytest.mark.parametrize(
    "entity",
    [
        LineEntity(start=(0, 0), end=(0, 0)),
        PolylineEntity(points=[(0, 0)]),
        RectangleEntity(width_mm=0, height_mm=5),
        CircleEntity(diameter_mm=0),
        PolygonEntity(radius_mm=4, sides=2),
        SlotEntity(length_mm=8, width_mm=8),
    ],
)
def test_invalid_sketch_entities_are_rejected(entity) -> None:
    sketch = SketchPlan(id="sketch", entities=[entity])
    plan = OperationPlan(project_name="invalid_sketch", operations=[sketch_operation(sketch)])

    with pytest.raises(OperationValidationError):
        validate_operation_plan(plan)


def test_arc_entity_degenerate_points_rejected() -> None:
    sketch = SketchPlan(
        id="arc",
        entities=[{"entity_type": "arc", "start": (0, 0), "mid": (0, 0), "end": (5, 0)}],
        closed=False,
    )
    plan = OperationPlan(project_name="bad_arc", operations=[sketch_operation(sketch)])

    with pytest.raises(OperationValidationError, match="arc points"):
        validate_operation_plan(plan)


def test_symmetric_extrude_and_step_stl_export(tmp_path) -> None:
    plan = OperationPlan(
        project_name="symmetric_extrude",
        operations=[
            sketch_operation(SketchPlan(id="profile", entities=[RectangleEntity(width_mm=20, height_mm=10)])),
            {"id": "solid", "operation_type": "extrude", "sketch_id": "profile", "distance_mm": 6, "symmetric": True},
        ],
    )

    result = execute_operation_plan(plan)
    step_path = generate_step(plan, tmp_path / "solid.step")
    stl_path = generate_stl(plan, tmp_path / "solid.stl")

    assert result.final_object.val().Volume() > 0
    assert step_path.stat().st_size > 0
    assert stl_path.stat().st_size > 0


def test_cut_extrude_blind_and_through_all_reduce_volume() -> None:
    base = OperationPlan(
        project_name="base",
        operations=[CreateBoxOperation(id="base", width_mm=60, depth_mm=40, height_mm=8)],
    )
    blind = OperationPlan(
        project_name="blind_pocket",
        operations=[
            CreateBoxOperation(id="base", width_mm=60, depth_mm=40, height_mm=8),
            sketch_operation(
                SketchPlan(
                    id="pocket",
                    origin=(0, 0, 4.1),
                    entities=[RectangleEntity(width_mm=28, height_mm=16)],
                )
            ),
            CutExtrudeOperation(id="cut", target_id="base", sketch_id="pocket", distance_mm=3),
        ],
    )
    through = blind.model_copy(
        update={
            "project_name": "through_pocket",
            "operations": [
                *blind.operations[:2],
                CutExtrudeOperation(id="cut", target_id="base", sketch_id="pocket", extent_type="through_all"),
            ],
        }
    )

    base_volume = execute_operation_plan(base).final_object.val().Volume()
    assert execute_operation_plan(blind).final_object.val().Volume() < base_volume
    assert execute_operation_plan(through).final_object.val().Volume() < base_volume


def test_loft_two_and_three_profile_solids() -> None:
    two_profile = OperationPlan(
        project_name="lofted_adapter",
        operations=[
            sketch_operation(SketchPlan(id="bottom", origin=(0, 0, 0), entities=[CircleEntity(diameter_mm=30)])),
            sketch_operation(SketchPlan(id="top", origin=(0, 0, 30), entities=[CircleEntity(diameter_mm=14)])),
            LoftOperation(id="loft", sketch_ids=["bottom", "top"]),
        ],
    )
    three_profile = OperationPlan(
        project_name="multi_loft",
        operations=[
            sketch_operation(SketchPlan(id="a", origin=(0, 0, 0), entities=[CircleEntity(diameter_mm=30)])),
            sketch_operation(SketchPlan(id="b", origin=(0, 0, 15), entities=[CircleEntity(diameter_mm=22)])),
            sketch_operation(SketchPlan(id="c", origin=(0, 0, 30), entities=[CircleEntity(diameter_mm=14)])),
            LoftOperation(id="loft", sketch_ids=["a", "b", "c"]),
        ],
    )

    assert execute_operation_plan(two_profile).final_object.val().Volume() > 0
    assert execute_operation_plan(three_profile).final_object.val().Volume() > 0


def test_loft_invalid_reference_rejected() -> None:
    plan = OperationPlan(
        project_name="bad_loft",
        operations=[
            sketch_operation(SketchPlan(id="bottom", entities=[CircleEntity(diameter_mm=20)])),
            LoftOperation(id="loft", sketch_ids=["bottom", "missing"]),
        ],
    )

    with pytest.raises(OperationValidationError, match="unknown or future"):
        validate_operation_plan(plan)


def test_sweep_straight_and_polyline_paths() -> None:
    straight = OperationPlan(
        project_name="straight_sweep",
        operations=[
            sketch_operation(SketchPlan(id="profile", plane="YZ", entities=[CircleEntity(diameter_mm=8)])),
            sketch_operation(
                SketchPlan(id="path", entities=[LineEntity(start=(0, 0), end=(40, 0))], closed=False)
            ),
            SweepOperation(id="sweep", profile_sketch_id="profile", path_sketch_id="path"),
        ],
    )
    polyline = OperationPlan(
        project_name="polyline_sweep",
        operations=[
            sketch_operation(SketchPlan(id="profile", plane="YZ", entities=[CircleEntity(diameter_mm=8)])),
            sketch_operation(
                SketchPlan(
                    id="path",
                    entities=[PolylineEntity(points=[(0, 0), (30, 0), (30, 20)], closed=False)],
                    closed=False,
                )
            ),
            SweepOperation(id="sweep", profile_sketch_id="profile", path_sketch_id="path"),
        ],
    )

    assert execute_operation_plan(straight).final_object.val().Volume() > 0
    assert execute_operation_plan(polyline).final_object.val().Volume() > 0


def test_shell_valid_and_invalid_thickness() -> None:
    valid = OperationPlan(
        project_name="open_shell",
        operations=[
            CreateBoxOperation(id="box", width_mm=40, depth_mm=30, height_mm=20),
            ShellOperation(id="shell", target_id="box", thickness_mm=2, remove_face_selector="top_face"),
        ],
    )
    invalid = OperationPlan(
        project_name="bad_shell",
        operations=[
            CreateBoxOperation(id="box", width_mm=20, depth_mm=20, height_mm=10),
            ShellOperation(id="shell", target_id="box", thickness_mm=8, remove_face_selector="top_face"),
        ],
    )

    assert execute_operation_plan(valid).final_object.val().Volume() > 0
    with pytest.raises(OperationExecutionError, match="shell failure"):
        execute_operation_plan(invalid)
    assert classify_failure(OperationExecutionError("shell failure: too thick")) == FailureCategory.SHELL_FAILURE


@pytest.mark.parametrize(
    "operation",
    [
        ThroughHoleOperation(id="hole", target_id="base", position=(0, 0), hole_diameter_mm=4),
        BlindHoleOperation(id="hole", target_id="base", position=(0, 0), hole_diameter_mm=4, depth_mm=3),
        CounterboreHoleOperation(
            id="hole",
            target_id="base",
            position=(0, 0),
            hole_diameter_mm=4,
            counterbore_diameter_mm=8,
            counterbore_depth_mm=2,
        ),
        CountersinkHoleOperation(
            id="hole",
            target_id="base",
            position=(0, 0),
            hole_diameter_mm=4,
            countersink_diameter_mm=8,
            angle_deg=90,
        ),
    ],
)
def test_advanced_holes_reduce_volume(operation) -> None:
    base = OperationPlan(
        project_name="base",
        operations=[CreateBoxOperation(id="base", width_mm=50, depth_mm=40, height_mm=8)],
    )
    holed = OperationPlan(
        project_name="holed",
        operations=[CreateBoxOperation(id="base", width_mm=50, depth_mm=40, height_mm=8), operation],
    )

    assert execute_operation_plan(holed).final_object.val().Volume() < execute_operation_plan(base).final_object.val().Volume()


def test_invalid_hole_geometry_rejected() -> None:
    plan = OperationPlan(
        project_name="bad_counterbore",
        operations=[
            CreateBoxOperation(id="base", width_mm=30, depth_mm=30, height_mm=5),
            CounterboreHoleOperation(
                id="hole",
                target_id="base",
                hole_diameter_mm=5,
                counterbore_diameter_mm=4,
                counterbore_depth_mm=2,
            ),
        ],
    )

    with pytest.raises(OperationValidationError, match="counterbore_diameter"):
        validate_operation_plan(plan)


def test_boss_rib_and_repeated_hole_patterns() -> None:
    plan = OperationPlan(
        project_name="features",
        operations=[
            CreateBoxOperation(id="base", width_mm=80, depth_mm=50, height_mm=6),
            BossOperation(id="boss", target_id="base", position=(0, 0), diameter_mm=18, height_mm=10),
            RibOperation(id="rib", target_id="boss", start=(-20, 0), end=(20, 0), thickness_mm=4, height_mm=8),
            RectangularHolePatternOperation(
                id="mounting_holes",
                target_id="rib",
                hole_diameter_mm=4,
                count_x=2,
                count_y=2,
                spacing_x_mm=54,
                spacing_y_mm=28,
            ),
            CircularHolePatternOperation(
                id="radial_holes",
                target_id="mounting_holes",
                hole_diameter_mm=3,
                count=4,
                radius_mm=12,
            ),
        ],
    )

    assert execute_operation_plan(plan).final_object.val().Volume() > 0


def test_raw_selector_rejected_by_schema() -> None:
    with pytest.raises(Exception):
        OperationPlan.model_validate(
            {
                "project_name": "raw_selector",
                "operations": [
                    {"id": "base", "operation_type": "create_box", "width_mm": 20, "depth_mm": 20, "height_mm": 5},
                    {
                        "id": "shell",
                        "operation_type": "shell",
                        "target_id": "base",
                        "thickness_mm": 1,
                        "remove_face_selector": ">Z",
                    },
                ],
            }
        )


def test_editor_can_modify_advanced_operation_fields() -> None:
    plan = OperationPlan(
        project_name="editable_advanced",
        operations=[
            CreateBoxOperation(id="base", width_mm=40, depth_mm=30, height_mm=12),
            ShellOperation(id="shell", target_id="base", thickness_mm=2, remove_face_selector="top_face"),
        ],
    )

    edited, summary = apply_edit(
        plan,
        ModifyOperationEdit(operation_id="shell", changes={"thickness_mm": 3}),
    )

    assert "shell" in summary
    assert edited.operations[1].thickness_mm == 3
