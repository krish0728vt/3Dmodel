from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from ai.schemas import CreateBoxOperation, OperationPlan, ThroughHoleOperation
from api.dependencies import get_project_store
from api.server import create_app
from parametrics.expressions import evaluate_expression
from parametrics.models import (
    CenteredRelationship,
    DependentDimensionRelationship,
    DesignParameter,
    EdgeOffsetRelationship,
    EqualSpacingRelationship,
    FixedRelationship,
)
from parametrics.resolver import ParametricResolutionError, resolve_design_intent
from projects.diff import diff_models
from projects.editor import apply_edit
from projects.manager import create_project_from_model
from projects.models import SetDesignParameterEdit
from projects.store import ProjectStore


def _ref(parameter_id: str) -> dict[str, object]:
    return {"expression_type": "parameter_ref", "parameter_id": parameter_id}


def _lit(value: float) -> dict[str, object]:
    return {"expression_type": "literal", "value": value}


def _expr(expression_type: str, left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    return {"expression_type": expression_type, "left": left, "right": right}


def _plate_plan(width: float = 100) -> OperationPlan:
    return OperationPlan(
        schema_version="1.2",
        project_name="param_plate",
        parameters=[
            DesignParameter(parameter_id="plate_width", name="Plate Width", value=width),
            DesignParameter(parameter_id="edge", name="Edge Offset", value=8),
        ],
        relationships=[
            FixedRelationship(relationship_id="bind_width", target="operations.base.width_mm", value=_ref("plate_width")),
            EdgeOffsetRelationship(
                relationship_id="right_hole_x",
                target="operations.right_hole.position.0",
                reference_object="base",
                reference_edge="right",
                offset_mm=_ref("edge"),
                axis="x",
            ),
            CenteredRelationship(
                relationship_id="center_hole_y",
                target_id="right_hole",
                reference_id="base",
                axes="y",
            ),
        ],
        operations=[
            CreateBoxOperation(id="base", width_mm=width, depth_mm=60, height_mm=5),
            ThroughHoleOperation(id="right_hole", target_id="base", position=(42, 0), hole_diameter_mm=5),
        ],
        final_object_id="right_hole",
    )


def test_safe_expression_tree_operations() -> None:
    parameters = {"a": 8, "b": 2}
    assert evaluate_expression(_expr("add", _ref("a"), _lit(4)), parameters) == 12
    assert evaluate_expression(_expr("subtract", _ref("a"), _ref("b")), parameters) == 6
    assert evaluate_expression(_expr("multiply", _ref("a"), _ref("b")), parameters) == 16
    assert evaluate_expression(_expr("divide", _ref("a"), _ref("b")), parameters) == 4
    assert evaluate_expression(_expr("min", _ref("a"), _lit(3)), parameters) == 3
    assert evaluate_expression(_expr("max", _ref("a"), _lit(3)), parameters) == 8
    with pytest.raises(Exception, match="DIVISION BY ZERO"):
        evaluate_expression(_expr("divide", _ref("a"), _lit(0)), parameters)
    with pytest.raises(Exception, match="MISSING PARAMETER"):
        evaluate_expression(_ref("missing"), parameters)


def test_edge_offset_survives_width_resize() -> None:
    plan = _plate_plan(width=100)
    resolved = resolve_design_intent(plan).resolved_model
    assert isinstance(resolved, OperationPlan)
    assert resolved.operations[1].position == (42, 0)

    edited, summary = apply_edit(plan, SetDesignParameterEdit(parameter_id="plate_width", value=120))
    assert isinstance(edited, OperationPlan)
    assert edited.operations[0].width_mm == 120
    assert edited.operations[1].position == (52, 0)
    assert "DRIVING CHANGES" in summary
    assert "DERIVED CHANGES" in summary


def test_equal_spacing_redistributes_after_resize() -> None:
    plan = OperationPlan(
        schema_version="1.2",
        project_name="spacing",
        parameters=[DesignParameter(parameter_id="usable", name="Usable Width", value=80)],
        relationships=[
            EqualSpacingRelationship(
                relationship_id="space",
                target_ids=["h1", "h2", "h3"],
                axis="x",
                start=_expr("multiply", _ref("usable"), _lit(-0.5)),
                end=_expr("multiply", _ref("usable"), _lit(0.5)),
            )
        ],
        operations=[
            CreateBoxOperation(id="base", width_mm=120, depth_mm=40, height_mm=5),
            ThroughHoleOperation(id="h1", target_id="base", position=(-40, 0), hole_diameter_mm=4),
            ThroughHoleOperation(id="h2", target_id="h1", position=(0, 0), hole_diameter_mm=4),
            ThroughHoleOperation(id="h3", target_id="h2", position=(40, 0), hole_diameter_mm=4),
        ],
        final_object_id="h3",
    )
    edited, _ = apply_edit(plan, SetDesignParameterEdit(parameter_id="usable", value=100))
    assert isinstance(edited, OperationPlan)
    assert [operation.position[0] for operation in edited.operations[1:]] == [-50, 0, 50]


def test_dependent_dimensions_cycle_missing_and_conflict() -> None:
    cycle_plan = _plate_plan()
    cycle_plan.parameters.extend(
        [
            DesignParameter(parameter_id="a", name="A", value=1, role="derived", editable=False),
            DesignParameter(parameter_id="b", name="B", value=1, role="derived", editable=False),
        ]
    )
    cycle_plan.relationships.extend(
        [
            DependentDimensionRelationship(relationship_id="a_from_b", target_parameter="a", expression=_expr("add", _ref("b"), _lit(1))),
            DependentDimensionRelationship(relationship_id="b_from_a", target_parameter="b", expression=_expr("add", _ref("a"), _lit(1))),
        ]
    )
    with pytest.raises(ParametricResolutionError, match="PARAMETRIC DEPENDENCY CYCLE"):
        resolve_design_intent(cycle_plan)

    missing_plan = _plate_plan()
    missing_plan.relationships.append(
        DependentDimensionRelationship(relationship_id="missing", target_parameter="edge", expression=_ref("unknown"))
    )
    with pytest.raises(ParametricResolutionError, match="MISSING PARAMETER"):
        resolve_design_intent(missing_plan)

    conflict_plan = _plate_plan()
    conflict_plan.relationships.append(
        EdgeOffsetRelationship(
            relationship_id="left_conflict",
            target="operations.right_hole.position.0",
            reference_object="base",
            reference_edge="left",
            offset_mm=8,
            axis="x",
        )
    )
    with pytest.raises(ParametricResolutionError, match="CONSTRAINT CONFLICT"):
        resolve_design_intent(conflict_plan)


def test_backward_compatible_schema_version_and_json_examples() -> None:
    legacy = OperationPlan(
        schema_version="1.1",
        project_name="legacy",
        operations=[CreateBoxOperation(id="box", width_mm=1, depth_mm=1, height_mm=1)],
    )
    assert legacy.parameters == []
    for path in [
        "plans/parametric_mounting_plate.json",
        "plans/parametric_boss_plate.json",
        "plans/parametric_hole_pattern.json",
        "plans/parametric_enclosure.json",
    ]:
        data = json.loads(open(path, encoding="utf-8").read())
        model = OperationPlan.model_validate(data) if "operations" in data else data
        if isinstance(model, OperationPlan):
            resolve_design_intent(model)


def test_parametric_diff_marks_driving_and_derived_changes() -> None:
    before = _plate_plan(width=100)
    after, _ = apply_edit(before, SetDesignParameterEdit(parameter_id="plate_width", value=120))
    summary = diff_models(before, after)
    assert "DRIVING CHANGES" in summary
    assert "Plate Width" in summary
    assert "DERIVED CHANGES" in summary
    assert "right_hole" in summary


def test_parametric_project_api(tmp_path) -> None:
    store = ProjectStore(tmp_path / "projects.db")
    project, _ = create_project_from_model(name="param", model=_plate_plan(), store=store)
    app = create_app()
    app.dependency_overrides[get_project_store] = lambda: store
    client = TestClient(app)

    assert client.get(f"/api/projects/{project.project_id}/parameters").status_code == 200
    assert client.get(f"/api/projects/{project.project_id}/relationships").status_code == 200
    resolved = client.get(f"/api/projects/{project.project_id}/resolved-design")
    assert resolved.status_code == 200
    assert resolved.json()["derived_values"]["operations.right_hole.position.0"] == 42

    response = client.post(
        f"/api/projects/{project.project_id}/parameters/plate_width",
        json={"value": 120, "instruction": "make the plate wider"},
    )
    assert response.status_code == 200
    assert "DRIVING CHANGES" in response.json()["change_summary"]

    validate = client.post("/api/parametrics/validate", json={"spec": _plate_plan().model_dump(mode="json")})
    assert validate.status_code == 200
    assert validate.json()["valid"] is True
