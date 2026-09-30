from __future__ import annotations

import math

import pytest

from ai.schemas import (
    BlindHoleOperation,
    BoxSpec,
    CreateBoxOperation,
    CutExtrudeOperation,
    ElectronicsEnclosureSpec,
    OperationPlan,
    RectangleEntity,
    ShellOperation,
    SketchPlan,
)
from cad.generator import generate_workplane
from engineering.analyzer import analyze_part
from engineering.geometry import calculate_geometry_metrics
from engineering.materials import UnknownMaterialError, get_material
from engineering.models import ManufacturingProcess
from engineering.units import UnitConversionError, convert_length, normalize_prompt_lengths_to_mm
from learning.classifier import classify_failure
from learning.models import FailureCategory


def test_unit_conversions_are_deterministic() -> None:
    assert convert_length(1, "inch") == pytest.approx(25.4)
    assert convert_length(4, "inches") == pytest.approx(101.6)
    assert convert_length(10, "cm") == pytest.approx(100)
    assert convert_length(1, "m") == pytest.approx(1000)
    assert convert_length(1, "ft") == pytest.approx(304.8)
    with pytest.raises(UnitConversionError):
        convert_length(1, "parsec")


def test_mixed_unit_prompt_normalization() -> None:
    prompt = "Create a plate 4 inches wide, 60 mm tall and 0.25 inches thick."

    normalized = normalize_prompt_lengths_to_mm(prompt)

    assert "101.6 mm wide" in normalized
    assert "60 mm tall" in normalized
    assert "6.35 mm thick" in normalized


def test_box_geometry_metrics_known_volume_area_and_center() -> None:
    part = generate_workplane(BoxSpec(width_mm=10, depth_mm=10, height_mm=10))

    metrics = calculate_geometry_metrics(part)

    assert metrics.volume_mm3 == pytest.approx(1000)
    assert metrics.surface_area_mm2 == pytest.approx(600)
    assert metrics.size.x_mm == pytest.approx(10)
    assert metrics.size.y_mm == pytest.approx(10)
    assert metrics.size.z_mm == pytest.approx(10)
    assert metrics.center_of_mass.x_mm == pytest.approx(0, abs=1e-6)


def test_cylinder_geometry_volume_within_tolerance() -> None:
    from ai.schemas import CylinderSpec

    metrics = calculate_geometry_metrics(generate_workplane(CylinderSpec(diameter_mm=10, height_mm=20)))

    assert metrics.volume_mm3 == pytest.approx(math.pi * 5 * 5 * 20, rel=0.01)


def test_mass_estimate_uses_cm3_and_material_density() -> None:
    report = analyze_part(BoxSpec(width_mm=10, depth_mm=10, height_mm=10), material_id="pla")

    assert report.material is not None
    assert report.material.density_g_cm3 == pytest.approx(1.24)
    assert report.mass_estimate is not None
    assert report.mass_estimate.volume_cm3 == pytest.approx(1)
    assert report.mass_estimate.mass_g == pytest.approx(1.24)
    assert report.mass_estimate.mass_kg == pytest.approx(0.00124)
    with pytest.raises(UnknownMaterialError):
        get_material("unobtainium")


def test_display_units_do_not_change_geometry() -> None:
    metric = analyze_part(BoxSpec(width_mm=101.6, depth_mm=25.4, height_mm=10), display_units="mm")
    imperial = analyze_part(BoxSpec(width_mm=101.6, depth_mm=25.4, height_mm=10), display_units="in")

    assert metric.geometry_metrics.volume_mm3 == imperial.geometry_metrics.volume_mm3
    assert imperial.display_metrics.x == pytest.approx(4)
    assert imperial.display_metrics.y == pytest.approx(1)


def test_3d_printing_warnings_for_thin_wall_small_hole_and_large_part() -> None:
    thin_enclosure = ElectronicsEnclosureSpec(
        internal_width_mm=260,
        internal_depth_mm=20,
        internal_height_mm=20,
        wall_thickness_mm=0.6,
        bottom_thickness_mm=1,
    )

    report = analyze_part(
        thin_enclosure,
        manufacturing_process=ManufacturingProcess.THREE_D_PRINTING,
    )

    warning_ids = {warning.warning_id for warning in report.warnings}
    assert "thin_wall_electronics_enclosure_wall" in warning_ids
    assert "build_volume_x" in warning_ids


def test_3d_printing_tiny_hole_warning() -> None:
    from ai.schemas import HoleSpec, MountingPlateSpec

    report = analyze_part(
        MountingPlateSpec(
            width_mm=40,
            height_mm=30,
            thickness_mm=4,
            holes=[HoleSpec(diameter_mm=1.5, x_mm=0, y_mm=0)],
        ),
        manufacturing_process=ManufacturingProcess.THREE_D_PRINTING,
    )

    assert any(warning.warning_id.startswith("small_hole") for warning in report.warnings)


def test_cnc_warnings_for_deep_hole_and_rectangular_pocket() -> None:
    plan = OperationPlan(
        project_name="cnc_warning",
        operations=[
            CreateBoxOperation(id="base", width_mm=50, depth_mm=40, height_mm=20),
            {
                "id": "pocket_profile",
                "operation_type": "create_sketch",
                "sketch": SketchPlan(
                    id="pocket_profile",
                    origin=(0, 0, 10.1),
                    entities=[RectangleEntity(width_mm=20, height_mm=10)],
                ).model_dump(mode="json"),
            },
            CutExtrudeOperation(id="pocket", target_id="base", sketch_id="pocket_profile", distance_mm=3),
            BlindHoleOperation(id="deep_hole", target_id="pocket", hole_diameter_mm=2, depth_mm=25),
        ],
    )

    report = analyze_part(plan, manufacturing_process=ManufacturingProcess.CNC_MACHINING)
    warning_ids = {warning.warning_id for warning in report.warnings}

    assert "internal_corner_pocket" in warning_ids
    assert "deep_small_hole_deep_hole" in warning_ids


def test_normal_part_reports_no_rule_warnings_for_selected_process() -> None:
    report = analyze_part(
        OperationPlan(
            project_name="normal_shell",
            operations=[
                CreateBoxOperation(id="box", width_mm=40, depth_mm=30, height_mm=20),
                ShellOperation(id="shell", target_id="box", thickness_mm=2, remove_face_selector="top_face"),
            ],
        ),
        manufacturing_process=ManufacturingProcess.THREE_D_PRINTING,
    )

    assert any(warning.warning_id == "no_rule_warnings" for warning in report.warnings)


def test_engineering_failures_are_classified() -> None:
    assert classify_failure(UnitConversionError("bad unit")) == FailureCategory.ENGINEERING_ANALYSIS_FAILURE
