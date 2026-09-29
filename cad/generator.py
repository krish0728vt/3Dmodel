from __future__ import annotations

from pathlib import Path

import cadquery as cq

from ai.schemas import (
    BoxSpec,
    CylinderSpec,
    ElectronicsEnclosureSpec,
    LBracketSpec,
    MountingPlateSpec,
    SpacerSpec,
    SupportedPartSpec,
)
from cad.operations import (
    cut_center_hole,
    cut_through_holes,
    cylinder,
    export_step,
    rounded_box,
    rounded_rectangle_plate,
)
from cad.validator import validate_part


DEFAULT_OUTPUT_PATH = Path("outputs/model.step")


def generate_part(spec: SupportedPartSpec) -> cq.Workplane:
    """Build a validated CadQuery model for any supported part."""

    validate_part(spec)
    if isinstance(spec, MountingPlateSpec):
        return build_mounting_plate(spec)
    if isinstance(spec, BoxSpec):
        return build_box(spec)
    if isinstance(spec, CylinderSpec):
        return build_cylinder(spec)
    if isinstance(spec, SpacerSpec):
        return build_spacer(spec)
    if isinstance(spec, LBracketSpec):
        return build_l_bracket(spec)
    if isinstance(spec, ElectronicsEnclosureSpec):
        return build_electronics_enclosure(spec)
    raise TypeError(f"Unsupported part specification: {type(spec).__name__}")


def build_mounting_plate(spec: MountingPlateSpec) -> cq.Workplane:
    """Build a validated CadQuery model for a rectangular mounting plate."""

    validate_part(spec)
    part = rounded_rectangle_plate(
        width_mm=spec.width_mm,
        height_mm=spec.height_mm,
        thickness_mm=spec.thickness_mm,
        corner_radius_mm=spec.corner_radius_mm,
    )
    holes = [(hole.diameter_mm, hole.x_mm, hole.y_mm) for hole in spec.holes]
    part = cut_through_holes(part, holes)

    return _as_single_solid(part)


def build_box(spec: BoxSpec) -> cq.Workplane:
    """Build a solid rectangular box."""

    validate_part(spec)
    part = rounded_box(
        width_mm=spec.width_mm,
        depth_mm=spec.depth_mm,
        height_mm=spec.height_mm,
        corner_radius_mm=spec.corner_radius_mm,
    )
    return _as_single_solid(part)


def build_cylinder(spec: CylinderSpec) -> cq.Workplane:
    """Build a cylinder with an optional center through hole."""

    validate_part(spec)
    part = cylinder(spec.diameter_mm, spec.height_mm)
    if spec.center_hole_diameter_mm is not None:
        part = cut_center_hole(part, spec.center_hole_diameter_mm)
    return _as_single_solid(part)


def build_spacer(spec: SpacerSpec) -> cq.Workplane:
    """Build a cylindrical spacer with a center through hole."""

    validate_part(spec)
    part = cylinder(spec.outer_diameter_mm, spec.height_mm)
    part = cut_center_hole(part, spec.inner_diameter_mm)
    return _as_single_solid(part)


def build_l_bracket(spec: LBracketSpec) -> cq.Workplane:
    """Build a simple 90-degree L bracket without face-specific holes."""

    validate_part(spec)
    horizontal_leg = (
        cq.Workplane("XY")
        .box(spec.width_mm, spec.leg_depth_mm, spec.thickness_mm)
        .translate((0, 0, spec.thickness_mm / 2))
    )
    vertical_leg = (
        cq.Workplane("XY")
        .box(spec.width_mm, spec.thickness_mm, spec.height_mm)
        .translate(
            (
                0,
                spec.leg_depth_mm / 2 - spec.thickness_mm / 2,
                spec.height_mm / 2,
            )
        )
    )
    part = horizontal_leg.union(vertical_leg)
    if spec.corner_radius_mm > 0:
        part = part.edges("|X").fillet(spec.corner_radius_mm)
    return _as_single_solid(part)


def build_electronics_enclosure(spec: ElectronicsEnclosureSpec) -> cq.Workplane:
    """Build a simple open-top electronics enclosure with optional mounting posts."""

    validate_part(spec)
    outer_width = spec.internal_width_mm + 2 * spec.wall_thickness_mm
    outer_depth = spec.internal_depth_mm + 2 * spec.wall_thickness_mm
    outer_height = spec.internal_height_mm + spec.bottom_thickness_mm

    part = (
        cq.Workplane("XY")
        .box(outer_width, outer_depth, outer_height)
        .translate((0, 0, outer_height / 2))
    )
    if spec.corner_radius_mm > 0:
        part = part.edges("|Z").fillet(spec.corner_radius_mm)

    cutter_height = spec.internal_height_mm + 1
    inner_cutter = (
        cq.Workplane("XY")
        .box(spec.internal_width_mm, spec.internal_depth_mm, cutter_height)
        .translate((0, 0, spec.bottom_thickness_mm + cutter_height / 2))
    )
    part = part.cut(inner_cutter)

    for post in spec.mounting_posts:
        post_solid = (
            cq.Workplane("XY")
            .circle(post.outer_diameter_mm / 2)
            .extrude(post.height_mm)
            .translate((post.x_mm, post.y_mm, spec.bottom_thickness_mm))
        )
        part = part.union(post_solid)

        hole_cutter_height = spec.bottom_thickness_mm + post.height_mm + 1
        hole_cutter = (
            cq.Workplane("XY")
            .circle(post.hole_diameter_mm / 2)
            .extrude(hole_cutter_height)
            .translate((post.x_mm, post.y_mm, -0.5))
        )
        part = part.cut(hole_cutter)

    return _as_single_solid(part)


def generate_step(
    spec: SupportedPartSpec,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    """Build and export a supported CAD part STEP file."""

    part = generate_part(spec)
    return export_step(part, output_path)


def _as_single_solid(part: cq.Workplane) -> cq.Workplane:
    solid = part.val()
    if isinstance(solid, cq.Solid):
        return cq.Workplane("XY").newObject([solid])

    solids = solid.Solids()
    if len(solids) != 1:
        raise ValueError(f"Expected one solid, found {len(solids)}.")
    return cq.Workplane("XY").newObject([solids[0]])
