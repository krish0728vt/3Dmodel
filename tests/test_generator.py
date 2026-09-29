from __future__ import annotations

import cadquery as cq
import pytest

from ai.schemas import (
    BoxSpec,
    CylinderSpec,
    ElectronicsEnclosureSpec,
    HoleSpec,
    LBracketSpec,
    MountingPlateSpec,
    MountingPostSpec,
    SpacerSpec,
    SupportedPartSpec,
)
from cad.generator import (
    build_box,
    build_cylinder,
    build_electronics_enclosure,
    build_l_bracket,
    build_mounting_plate,
    build_spacer,
    generate_part,
    generate_step,
)
from cad.validator import GeometryValidationError, validate_part


def sample_spec() -> MountingPlateSpec:
    return MountingPlateSpec(
        width_mm=100,
        height_mm=60,
        thickness_mm=5,
        corner_radius_mm=4,
        holes=[
            HoleSpec(diameter_mm=5, x_mm=-42, y_mm=-22),
            HoleSpec(diameter_mm=5, x_mm=42, y_mm=-22),
            HoleSpec(diameter_mm=5, x_mm=-42, y_mm=22),
            HoleSpec(diameter_mm=5, x_mm=42, y_mm=22),
        ],
    )


def test_valid_mounting_plate_produces_cadquery_solid() -> None:
    part = build_mounting_plate(sample_spec())
    solid = part.val()

    assert isinstance(part, cq.Workplane)
    assert isinstance(solid, cq.Solid)
    assert solid.Volume() > 0


def test_step_export_succeeds(tmp_path) -> None:
    output_path = tmp_path / "model.step"

    generated_path = generate_step(sample_spec(), output_path)

    assert generated_path == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 0


@pytest.mark.parametrize(
    "spec",
    [
        BoxSpec(width_mm=50, depth_mm=30, height_mm=10, corner_radius_mm=2),
        CylinderSpec(diameter_mm=30, height_mm=50),
        CylinderSpec(diameter_mm=30, height_mm=50, center_hole_diameter_mm=10),
        SpacerSpec(outer_diameter_mm=20, inner_diameter_mm=6, height_mm=10),
        LBracketSpec(width_mm=60, height_mm=40, leg_depth_mm=30, thickness_mm=4),
        ElectronicsEnclosureSpec(
            internal_width_mm=70,
            internal_depth_mm=45,
            internal_height_mm=25,
            wall_thickness_mm=2,
            bottom_thickness_mm=2,
            corner_radius_mm=2,
        ),
        ElectronicsEnclosureSpec(
            internal_width_mm=70,
            internal_depth_mm=45,
            internal_height_mm=25,
            wall_thickness_mm=2,
            bottom_thickness_mm=2,
            corner_radius_mm=2,
            mounting_posts=[
                MountingPostSpec(
                    x_mm=-25,
                    y_mm=-12,
                    outer_diameter_mm=6,
                    hole_diameter_mm=3.2,
                    height_mm=8,
                ),
                MountingPostSpec(
                    x_mm=25,
                    y_mm=-12,
                    outer_diameter_mm=6,
                    hole_diameter_mm=3.2,
                    height_mm=8,
                ),
                MountingPostSpec(
                    x_mm=-25,
                    y_mm=12,
                    outer_diameter_mm=6,
                    hole_diameter_mm=3.2,
                    height_mm=8,
                ),
                MountingPostSpec(
                    x_mm=25,
                    y_mm=12,
                    outer_diameter_mm=6,
                    hole_diameter_mm=3.2,
                    height_mm=8,
                ),
            ],
        ),
    ],
)
def test_supported_parts_produce_cadquery_solids(spec: SupportedPartSpec) -> None:
    part = generate_part(spec)

    assert isinstance(part, cq.Workplane)
    assert isinstance(part.val(), cq.Solid)
    assert part.val().Volume() > 0


def test_specific_builders_produce_valid_solids() -> None:
    specs_and_builders = [
        (BoxSpec(width_mm=50, depth_mm=30, height_mm=10, corner_radius_mm=2), build_box),
        (CylinderSpec(diameter_mm=30, height_mm=50, center_hole_diameter_mm=10), build_cylinder),
        (SpacerSpec(outer_diameter_mm=20, inner_diameter_mm=6, height_mm=10), build_spacer),
        (LBracketSpec(width_mm=60, height_mm=40, leg_depth_mm=30, thickness_mm=4), build_l_bracket),
        (
            ElectronicsEnclosureSpec(
                internal_width_mm=70,
                internal_depth_mm=45,
                internal_height_mm=25,
                wall_thickness_mm=2,
                bottom_thickness_mm=2,
                corner_radius_mm=2,
            ),
            build_electronics_enclosure,
        ),
    ]

    for spec, builder in specs_and_builders:
        assert builder(spec).val().Volume() > 0


def test_every_supported_part_exports_step(tmp_path) -> None:
    specs: list[SupportedPartSpec] = [
        sample_spec(),
        BoxSpec(width_mm=50, depth_mm=30, height_mm=10, corner_radius_mm=2),
        CylinderSpec(diameter_mm=30, height_mm=50, center_hole_diameter_mm=10),
        SpacerSpec(outer_diameter_mm=20, inner_diameter_mm=6, height_mm=10),
        LBracketSpec(width_mm=60, height_mm=40, leg_depth_mm=30, thickness_mm=4),
        ElectronicsEnclosureSpec(
            internal_width_mm=70,
            internal_depth_mm=45,
            internal_height_mm=25,
            wall_thickness_mm=2,
            bottom_thickness_mm=2,
            corner_radius_mm=2,
        ),
    ]

    for spec in specs:
        output_path = tmp_path / f"{spec.part_type}.step"
        generate_step(spec, output_path)
        assert output_path.exists()
        assert output_path.stat().st_size > 0


def test_invalid_new_part_specs_are_rejected() -> None:
    invalid_specs: list[SupportedPartSpec] = [
        BoxSpec(width_mm=-50, depth_mm=30, height_mm=10),
        BoxSpec(width_mm=50, depth_mm=30, height_mm=10, corner_radius_mm=20),
        CylinderSpec(diameter_mm=30, height_mm=50, center_hole_diameter_mm=30),
        SpacerSpec(outer_diameter_mm=6, inner_diameter_mm=20, height_mm=10),
        LBracketSpec(width_mm=60, height_mm=40, leg_depth_mm=30, thickness_mm=0),
        ElectronicsEnclosureSpec(
            internal_width_mm=70,
            internal_depth_mm=45,
            internal_height_mm=25,
            wall_thickness_mm=0,
            bottom_thickness_mm=2,
        ),
        ElectronicsEnclosureSpec(
            internal_width_mm=70,
            internal_depth_mm=45,
            internal_height_mm=25,
            wall_thickness_mm=2,
            bottom_thickness_mm=2,
            mounting_posts=[
                MountingPostSpec(
                    x_mm=40,
                    y_mm=0,
                    outer_diameter_mm=6,
                    hole_diameter_mm=3,
                    height_mm=8,
                )
            ],
        ),
        ElectronicsEnclosureSpec(
            internal_width_mm=70,
            internal_depth_mm=45,
            internal_height_mm=25,
            wall_thickness_mm=2,
            bottom_thickness_mm=2,
            mounting_posts=[
                MountingPostSpec(
                    x_mm=0,
                    y_mm=0,
                    outer_diameter_mm=6,
                    hole_diameter_mm=6,
                    height_mm=8,
                )
            ],
        ),
    ]

    for spec in invalid_specs:
        with pytest.raises(GeometryValidationError):
            validate_part(spec)
