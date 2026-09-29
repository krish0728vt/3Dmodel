from __future__ import annotations

from ai.schemas import (
    BoxSpec,
    CylinderSpec,
    ElectronicsEnclosureSpec,
    LBracketSpec,
    MountingPlateSpec,
    SpacerSpec,
    SupportedPartSpec,
)


class GeometryValidationError(ValueError):
    """Raised when a CAD specification cannot produce valid geometry."""


def validate_part(spec: SupportedPartSpec) -> None:
    """Validate any supported CAD part specification."""

    if isinstance(spec, MountingPlateSpec):
        validate_mounting_plate(spec)
    elif isinstance(spec, BoxSpec):
        validate_box(spec)
    elif isinstance(spec, CylinderSpec):
        validate_cylinder(spec)
    elif isinstance(spec, SpacerSpec):
        validate_spacer(spec)
    elif isinstance(spec, LBracketSpec):
        validate_l_bracket(spec)
    elif isinstance(spec, ElectronicsEnclosureSpec):
        validate_electronics_enclosure(spec)
    else:
        raise GeometryValidationError(f"Unsupported part specification: {type(spec).__name__}")


def validate_mounting_plate(spec: MountingPlateSpec) -> None:
    """Validate a mounting plate before geometry creation."""

    errors: list[str] = []

    if spec.width_mm <= 0:
        errors.append("width_mm must be greater than 0.")
    if spec.height_mm <= 0:
        errors.append("height_mm must be greater than 0.")
    if spec.thickness_mm <= 0:
        errors.append("thickness_mm must be greater than 0.")
    if spec.corner_radius_mm < 0:
        errors.append("corner_radius_mm must be greater than or equal to 0.")

    if spec.width_mm > 0 and spec.height_mm > 0:
        max_radius = min(spec.width_mm, spec.height_mm) / 2
        if spec.corner_radius_mm > max_radius:
            errors.append(
                "corner_radius_mm cannot exceed half of the smaller plate dimension "
                f"({max_radius:g} mm)."
            )

    half_width = spec.width_mm / 2
    half_height = spec.height_mm / 2

    for index, hole in enumerate(spec.holes, start=1):
        if hole.diameter_mm <= 0:
            errors.append(f"holes[{index}].diameter_mm must be greater than 0.")
            continue

        radius = hole.diameter_mm / 2
        if abs(hole.x_mm) + radius > half_width:
            errors.append(
                f"holes[{index}] intersects or extends beyond the left/right plate edge."
            )
        if abs(hole.y_mm) + radius > half_height:
            errors.append(
                f"holes[{index}] intersects or extends beyond the top/bottom plate edge."
            )

    if errors:
        raise GeometryValidationError("Invalid mounting plate specification: " + " ".join(errors))


def validate_box(spec: BoxSpec) -> None:
    errors: list[str] = []
    if spec.width_mm <= 0:
        errors.append("width_mm must be greater than 0.")
    if spec.depth_mm <= 0:
        errors.append("depth_mm must be greater than 0.")
    if spec.height_mm <= 0:
        errors.append("height_mm must be greater than 0.")
    if spec.corner_radius_mm < 0:
        errors.append("corner_radius_mm must be greater than or equal to 0.")
    if spec.width_mm > 0 and spec.depth_mm > 0:
        max_radius = min(spec.width_mm, spec.depth_mm) / 2
        if spec.corner_radius_mm > max_radius:
            errors.append(
                "corner_radius_mm cannot exceed half of the smaller box footprint dimension "
                f"({max_radius:g} mm)."
            )
    if errors:
        raise GeometryValidationError("Invalid box specification: " + " ".join(errors))


def validate_cylinder(spec: CylinderSpec) -> None:
    errors: list[str] = []
    if spec.diameter_mm <= 0:
        errors.append("diameter_mm must be greater than 0.")
    if spec.height_mm <= 0:
        errors.append("height_mm must be greater than 0.")
    if spec.center_hole_diameter_mm is not None:
        if spec.center_hole_diameter_mm <= 0:
            errors.append("center_hole_diameter_mm must be greater than 0.")
        elif spec.diameter_mm > 0 and spec.center_hole_diameter_mm >= spec.diameter_mm:
            errors.append("center_hole_diameter_mm must be smaller than diameter_mm.")
    if errors:
        raise GeometryValidationError("Invalid cylinder specification: " + " ".join(errors))


def validate_spacer(spec: SpacerSpec) -> None:
    errors: list[str] = []
    if spec.outer_diameter_mm <= 0:
        errors.append("outer_diameter_mm must be greater than 0.")
    if spec.inner_diameter_mm <= 0:
        errors.append("inner_diameter_mm must be greater than 0.")
    if spec.height_mm <= 0:
        errors.append("height_mm must be greater than 0.")
    if spec.outer_diameter_mm > 0 and spec.inner_diameter_mm > 0:
        if spec.inner_diameter_mm >= spec.outer_diameter_mm:
            errors.append("inner_diameter_mm must be smaller than outer_diameter_mm.")
    if errors:
        raise GeometryValidationError("Invalid spacer specification: " + " ".join(errors))


def validate_l_bracket(spec: LBracketSpec) -> None:
    errors: list[str] = []
    if spec.width_mm <= 0:
        errors.append("width_mm must be greater than 0.")
    if spec.height_mm <= 0:
        errors.append("height_mm must be greater than 0.")
    if spec.leg_depth_mm <= 0:
        errors.append("leg_depth_mm must be greater than 0.")
    if spec.thickness_mm <= 0:
        errors.append("thickness_mm must be greater than 0.")
    if spec.corner_radius_mm < 0:
        errors.append("corner_radius_mm must be greater than or equal to 0.")
    if spec.thickness_mm > 0:
        if spec.height_mm > 0 and spec.thickness_mm > spec.height_mm:
            errors.append("thickness_mm cannot exceed height_mm.")
        if spec.leg_depth_mm > 0 and spec.thickness_mm > spec.leg_depth_mm:
            errors.append("thickness_mm cannot exceed leg_depth_mm.")
        max_radius = spec.thickness_mm / 2
        if spec.corner_radius_mm > max_radius:
            errors.append(f"corner_radius_mm cannot exceed half the thickness ({max_radius:g} mm).")
    if spec.holes:
        errors.append("L bracket holes are reserved for a future milestone.")
    if errors:
        raise GeometryValidationError("Invalid L bracket specification: " + " ".join(errors))


def validate_electronics_enclosure(spec: ElectronicsEnclosureSpec) -> None:
    errors: list[str] = []
    if spec.internal_width_mm <= 0:
        errors.append("internal_width_mm must be greater than 0.")
    if spec.internal_depth_mm <= 0:
        errors.append("internal_depth_mm must be greater than 0.")
    if spec.internal_height_mm <= 0:
        errors.append("internal_height_mm must be greater than 0.")
    if spec.wall_thickness_mm <= 0:
        errors.append("wall_thickness_mm must be greater than 0.")
    if spec.bottom_thickness_mm <= 0:
        errors.append("bottom_thickness_mm must be greater than 0.")
    if spec.corner_radius_mm < 0:
        errors.append("corner_radius_mm must be greater than or equal to 0.")

    outer_width = spec.internal_width_mm + 2 * spec.wall_thickness_mm
    outer_depth = spec.internal_depth_mm + 2 * spec.wall_thickness_mm
    if outer_width > 0 and outer_depth > 0:
        max_radius = min(outer_width, outer_depth) / 2
        if spec.corner_radius_mm > max_radius:
            errors.append(
                "corner_radius_mm cannot exceed half of the smaller outside enclosure dimension "
                f"({max_radius:g} mm)."
            )

    half_internal_width = spec.internal_width_mm / 2
    half_internal_depth = spec.internal_depth_mm / 2
    for index, post in enumerate(spec.mounting_posts, start=1):
        if post.outer_diameter_mm <= 0:
            errors.append(f"mounting_posts[{index}].outer_diameter_mm must be greater than 0.")
            continue
        if post.hole_diameter_mm <= 0:
            errors.append(f"mounting_posts[{index}].hole_diameter_mm must be greater than 0.")
        elif post.hole_diameter_mm >= post.outer_diameter_mm:
            errors.append(
                f"mounting_posts[{index}].hole_diameter_mm must be smaller than outer_diameter_mm."
            )
        if post.height_mm <= 0:
            errors.append(f"mounting_posts[{index}].height_mm must be greater than 0.")
        elif spec.internal_height_mm > 0 and post.height_mm > spec.internal_height_mm:
            errors.append(
                f"mounting_posts[{index}].height_mm cannot exceed internal_height_mm."
            )

        radius = post.outer_diameter_mm / 2
        if abs(post.x_mm) + radius > half_internal_width:
            errors.append(f"mounting_posts[{index}] does not fit inside the internal width.")
        if abs(post.y_mm) + radius > half_internal_depth:
            errors.append(f"mounting_posts[{index}] does not fit inside the internal depth.")

    if errors:
        raise GeometryValidationError(
            "Invalid electronics enclosure specification: " + " ".join(errors)
        )
