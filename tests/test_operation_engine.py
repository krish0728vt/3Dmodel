from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ai.schemas import (
    BooleanCutOperation,
    BooleanUnionOperation,
    ChamferOperation,
    CircularPatternOperation,
    CreateBoxOperation,
    CreateCylinderOperation,
    CreateSketchCircleOperation,
    CreateSketchRectangleOperation,
    CutHoleOperation,
    ExtrudeOperation,
    FilletOperation,
    LinearPatternOperation,
    MirrorOperation,
    OperationPlan,
    RevolveOperation,
)
from cad.generator import generate_step
from cad.operation_executor import execute_operation_plan
from cad.operation_validator import OperationValidationError, validate_operation_plan


def test_valid_operation_plan_schema_and_validation() -> None:
    plan = OperationPlan(
        project_name="valid_box",
        operations=[CreateBoxOperation(id="box", width_mm=10, depth_mm=20, height_mm=5)],
    )

    validate_operation_plan(plan)


def test_duplicate_ids_are_rejected() -> None:
    plan = OperationPlan(
        project_name="duplicate",
        operations=[
            CreateBoxOperation(id="box", width_mm=10, depth_mm=20, height_mm=5),
            CreateCylinderOperation(id="box", diameter_mm=5, height_mm=5),
        ],
    )

    with pytest.raises(OperationValidationError, match="duplicate"):
        validate_operation_plan(plan)


def test_forward_references_are_rejected() -> None:
    plan = OperationPlan(
        project_name="forward_reference",
        operations=[
            BooleanUnionOperation(id="combined", target_id="base", tool_id="boss"),
            CreateBoxOperation(id="base", width_mm=10, depth_mm=20, height_mm=5),
            CreateCylinderOperation(id="boss", diameter_mm=5, height_mm=5),
        ],
    )

    with pytest.raises(OperationValidationError, match="unknown or future"):
        validate_operation_plan(plan)


def test_invalid_dimensions_are_rejected() -> None:
    plan = OperationPlan(
        project_name="bad_dimensions",
        operations=[CreateBoxOperation(id="box", width_mm=0, depth_mm=20, height_mm=5)],
    )

    with pytest.raises(OperationValidationError, match="width_mm"):
        validate_operation_plan(plan)


def test_invalid_plane_and_axis_are_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        OperationPlan.model_validate(
            {
                "project_name": "bad_plane",
                "operations": [
                    {
                        "id": "sketch",
                        "operation_type": "create_sketch_rectangle",
                        "width_mm": 10,
                        "height_mm": 5,
                        "plane": "AB",
                    }
                ],
            }
        )

    with pytest.raises(ValidationError):
        OperationPlan.model_validate(
            {
                "project_name": "bad_axis",
                "operations": [
                    {
                        "id": "pin",
                        "operation_type": "create_cylinder",
                        "diameter_mm": 5,
                        "height_mm": 5,
                        "axis": "q",
                    }
                ],
            }
        )


def test_invalid_pattern_count_is_rejected() -> None:
    plan = OperationPlan(
        project_name="bad_pattern",
        operations=[
            CreateCylinderOperation(id="pin", diameter_mm=5, height_mm=5),
            LinearPatternOperation(id="pattern", target_id="pin", direction="x", spacing_mm=10, count=1),
        ],
    )

    with pytest.raises(OperationValidationError, match="count"):
        validate_operation_plan(plan)


@pytest.mark.parametrize(
    "plan",
    [
        OperationPlan(
            project_name="create_box",
            operations=[CreateBoxOperation(id="box", width_mm=10, depth_mm=20, height_mm=5)],
        ),
        OperationPlan(
            project_name="create_cylinder",
            operations=[CreateCylinderOperation(id="cyl", diameter_mm=10, height_mm=20)],
        ),
        OperationPlan(
            project_name="rectangle_extrude",
            operations=[
                CreateSketchRectangleOperation(id="sketch", width_mm=10, height_mm=5),
                ExtrudeOperation(id="solid", sketch_id="sketch", distance_mm=3),
            ],
        ),
        OperationPlan(
            project_name="circle_extrude",
            operations=[
                CreateSketchCircleOperation(id="sketch", diameter_mm=10),
                ExtrudeOperation(id="solid", sketch_id="sketch", distance_mm=3),
            ],
        ),
        OperationPlan(
            project_name="revolve",
            operations=[
                CreateSketchRectangleOperation(
                    id="profile",
                    width_mm=2,
                    height_mm=10,
                    plane="XZ",
                    center=(5, 0, 0),
                ),
                RevolveOperation(id="solid", sketch_id="profile", axis="z"),
            ],
        ),
        OperationPlan(
            project_name="boolean_union",
            operations=[
                CreateBoxOperation(id="base", width_mm=20, depth_mm=20, height_mm=5),
                CreateCylinderOperation(id="boss", diameter_mm=8, height_mm=10, center=(0, 0, 7.5)),
                BooleanUnionOperation(id="combined", target_id="base", tool_id="boss"),
            ],
        ),
        OperationPlan(
            project_name="boolean_cut",
            operations=[
                CreateBoxOperation(id="base", width_mm=20, depth_mm=20, height_mm=5),
                CreateCylinderOperation(id="tool", diameter_mm=5, height_mm=8),
                BooleanCutOperation(id="cut", target_id="base", tool_id="tool"),
            ],
        ),
        OperationPlan(
            project_name="fillet",
            operations=[
                CreateBoxOperation(id="base", width_mm=20, depth_mm=20, height_mm=5),
                FilletOperation(id="filleted", target_id="base", radius_mm=1, edge_selector="vertical_edges"),
            ],
        ),
        OperationPlan(
            project_name="chamfer",
            operations=[
                CreateBoxOperation(id="base", width_mm=20, depth_mm=20, height_mm=5),
                ChamferOperation(id="chamfered", target_id="base", distance_mm=1, edge_selector="vertical_edges"),
            ],
        ),
        OperationPlan(
            project_name="mirror",
            operations=[
                CreateBoxOperation(id="half", width_mm=5, depth_mm=5, height_mm=5, center=(5, 0, 0)),
                MirrorOperation(id="mirrored", target_id="half", plane="YZ"),
            ],
        ),
        OperationPlan(
            project_name="linear_pattern",
            operations=[
                CreateCylinderOperation(id="pin", diameter_mm=3, height_mm=5),
                LinearPatternOperation(id="pattern", target_id="pin", direction="x", spacing_mm=8, count=3),
            ],
        ),
        OperationPlan(
            project_name="circular_pattern",
            operations=[
                CreateCylinderOperation(id="pin", diameter_mm=3, height_mm=5, center=(10, 0, 0)),
                CircularPatternOperation(id="pattern", target_id="pin", axis="z", count=4, angle_deg=360),
            ],
        ),
    ],
)
def test_operation_plans_produce_exportable_geometry(plan: OperationPlan) -> None:
    result = execute_operation_plan(plan)

    assert result.final_object.val().Volume() > 0


def test_cut_hole_reduces_volume() -> None:
    base = OperationPlan(
        project_name="base",
        operations=[CreateBoxOperation(id="base", width_mm=20, depth_mm=20, height_mm=5)],
    )
    holed = OperationPlan(
        project_name="holed",
        operations=[
            CreateBoxOperation(id="base", width_mm=20, depth_mm=20, height_mm=5),
            CutHoleOperation(id="hole", target_id="base", diameter_mm=5, position=(0, 0), direction="z"),
        ],
    )

    assert execute_operation_plan(holed).final_object.val().Volume() < execute_operation_plan(base).final_object.val().Volume()


def test_operation_plan_step_export(tmp_path) -> None:
    plan = OperationPlan(
        project_name="export_box",
        operations=[CreateBoxOperation(id="box", width_mm=10, depth_mm=20, height_mm=5)],
    )
    output_path = tmp_path / "operation.step"

    generate_step(plan, output_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_checked_in_example_plans_execute_and_export(tmp_path) -> None:
    for plan_path in Path("plans").glob("*.json"):
        plan = OperationPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        output_path = tmp_path / f"{plan.project_name}.step"

        generate_step(plan, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0
