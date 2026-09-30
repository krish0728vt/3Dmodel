from __future__ import annotations

from pathlib import Path

import cadquery as cq


def rounded_rectangle_plate(
    width_mm: float,
    height_mm: float,
    thickness_mm: float,
    corner_radius_mm: float,
) -> cq.Workplane:
    """Create a centered rectangular plate, optionally with rounded outside corners."""

    part = cq.Workplane("XY").box(width_mm, height_mm, thickness_mm)
    if corner_radius_mm > 0:
        part = part.edges("|Z").fillet(corner_radius_mm)

    return part


def rounded_box(
    width_mm: float,
    depth_mm: float,
    height_mm: float,
    corner_radius_mm: float = 0,
) -> cq.Workplane:
    """Create a centered solid box, optionally filleting vertical edges."""

    part = cq.Workplane("XY").box(width_mm, depth_mm, height_mm)
    if corner_radius_mm > 0:
        part = part.edges("|Z").fillet(corner_radius_mm)
    return part


def cylinder(
    diameter_mm: float,
    height_mm: float,
) -> cq.Workplane:
    """Create a cylinder centered on the XY origin."""

    return cq.Workplane("XY").circle(diameter_mm / 2).extrude(height_mm)


def cut_center_hole(
    part: cq.Workplane,
    diameter_mm: float,
) -> cq.Workplane:
    """Cut a centered through hole through a part from its top face."""

    return part.faces(">Z").workplane().hole(diameter_mm)


def cut_through_holes(
    part: cq.Workplane,
    holes: list[tuple[float, float, float]],
) -> cq.Workplane:
    """Cut through holes from the top face at the requested XY coordinates."""

    if not holes:
        return part

    points = [(x_mm, y_mm) for diameter_mm, x_mm, y_mm in holes]
    diameters = {diameter_mm for diameter_mm, _, _ in holes}

    if len(diameters) == 1:
        diameter_mm = next(iter(diameters))
        return part.faces(">Z").workplane().pushPoints(points).hole(diameter_mm)

    result = part
    for diameter_mm, x_mm, y_mm in holes:
        result = result.faces(">Z").workplane().pushPoints([(x_mm, y_mm)]).hole(diameter_mm)
    return result


def export_step(part: cq.Workplane, output_path: str | Path) -> Path:
    """Export a CadQuery part to STEP, creating the parent directory if needed."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(part, str(path))
    return path


def export_stl(
    part: cq.Workplane,
    output_path: str | Path,
    *,
    tolerance: float = 0.1,
    angular_tolerance: float = 0.1,
) -> Path:
    """Export a CadQuery part to STL for browser preview, creating the parent directory."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(part, str(path), tolerance=tolerance, angularTolerance=angular_tolerance)
    return path
