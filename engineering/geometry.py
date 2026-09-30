from __future__ import annotations

import cadquery as cq

from engineering.models import BoundingBoxMetrics, GeometryMetrics, PointMetrics, SizeMetrics


class GeometryAnalysisError(ValueError):
    """Raised when a CadQuery shape cannot be measured safely."""


def calculate_geometry_metrics(part: cq.Workplane) -> GeometryMetrics:
    shape = part.val()
    solids = shape.Solids() if hasattr(shape, "Solids") else []
    solid_count = len(solids) if solids else (1 if isinstance(shape, cq.Solid) else 0)
    if solid_count <= 0:
        raise GeometryAnalysisError("No measurable solid found.")
    volume = float(shape.Volume())
    if volume <= 0:
        raise GeometryAnalysisError("Measured solid has zero volume.")
    area = float(shape.Area())
    bbox = shape.BoundingBox()
    center = shape.Center()
    return GeometryMetrics(
        volume_mm3=volume,
        surface_area_mm2=area,
        bounding_box=BoundingBoxMetrics(
            min_x_mm=float(bbox.xmin),
            min_y_mm=float(bbox.ymin),
            min_z_mm=float(bbox.zmin),
            max_x_mm=float(bbox.xmax),
            max_y_mm=float(bbox.ymax),
            max_z_mm=float(bbox.zmax),
        ),
        size=SizeMetrics(x_mm=float(bbox.xlen), y_mm=float(bbox.ylen), z_mm=float(bbox.zlen)),
        center_of_mass=PointMetrics(x_mm=float(center.x), y_mm=float(center.y), z_mm=float(center.z)),
        solid_count=solid_count,
        valid=True,
    )
