from __future__ import annotations

import math
from pathlib import Path

from ai.schemas import (
    CreateSketchCircleOperation,
    CreateSketchOperation,
    CreateSketchRectangleOperation,
    OperationPlan,
    SketchPlan,
)


def export_plan_sketch_dxf(plan: OperationPlan, path: Path) -> Path:
    sketches = _sketches_from_plan(plan)
    if not sketches:
        raise ValueError("DXF export requires a structured 2D sketch source.")
    lines = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for sketch in sketches:
        _append_sketch(lines, sketch)
    lines.extend(["0", "ENDSEC", "0", "EOF"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def _sketches_from_plan(plan: OperationPlan) -> list[SketchPlan]:
    sketches: list[SketchPlan] = []
    for operation in plan.operations:
        if isinstance(operation, CreateSketchOperation):
            sketches.append(operation.sketch)
        elif isinstance(operation, CreateSketchRectangleOperation):
            sketches.append(
                SketchPlan(
                    id=operation.id,
                    plane=operation.plane,
                    origin=operation.center,
                    entities=[{"entity_type": "rectangle", "width_mm": operation.width_mm, "height_mm": operation.height_mm}],
                )
            )
        elif isinstance(operation, CreateSketchCircleOperation):
            sketches.append(
                SketchPlan(
                    id=operation.id,
                    plane=operation.plane,
                    origin=operation.center,
                    entities=[{"entity_type": "circle", "diameter_mm": operation.diameter_mm}],
                )
            )
    return sketches


def _append_sketch(lines: list[str], sketch: SketchPlan) -> None:
    if sketch.plane != "XY":
        raise ValueError("DXF export currently supports XY sketches only.")
    ox, oy, _ = sketch.origin
    for entity in sketch.entities:
        entity_type = entity.entity_type
        if entity_type == "rectangle":
            cx, cy = entity.center
            half_w = entity.width_mm / 2
            half_h = entity.height_mm / 2
            points = [
                (ox + cx - half_w, oy + cy - half_h),
                (ox + cx + half_w, oy + cy - half_h),
                (ox + cx + half_w, oy + cy + half_h),
                (ox + cx - half_w, oy + cy + half_h),
            ]
            _append_lwpolyline(lines, points, closed=True, layer="OUTLINE")
        elif entity_type == "circle":
            cx, cy = entity.center
            _append_circle(lines, ox + cx, oy + cy, entity.diameter_mm / 2, layer="HOLES")
        elif entity_type == "slot":
            _append_slot(lines, ox + entity.center[0], oy + entity.center[1], entity.length_mm, entity.width_mm, entity.rotation_deg)
        elif entity_type == "line":
            _append_line(lines, ox + entity.start[0], oy + entity.start[1], ox + entity.end[0], oy + entity.end[1], "OUTLINE")
        elif entity_type == "polyline":
            _append_lwpolyline(lines, [(ox + x, oy + y) for x, y in entity.points], closed=entity.closed, layer="OUTLINE")
        elif entity_type == "polygon":
            points = []
            for index in range(entity.sides):
                angle = math.radians(entity.rotation_deg + 360 * index / entity.sides)
                points.append((ox + entity.center[0] + math.cos(angle) * entity.radius_mm, oy + entity.center[1] + math.sin(angle) * entity.radius_mm))
            _append_lwpolyline(lines, points, closed=True, layer="OUTLINE")
        else:
            raise ValueError(f"DXF export does not support sketch entity: {entity_type}")


def _append_lwpolyline(lines: list[str], points: list[tuple[float, float]], *, closed: bool, layer: str) -> None:
    lines.extend(["0", "LWPOLYLINE", "8", layer, "90", str(len(points)), "70", "1" if closed else "0"])
    for x, y in points:
        lines.extend(["10", f"{x:.6f}", "20", f"{y:.6f}"])


def _append_circle(lines: list[str], x: float, y: float, radius: float, *, layer: str) -> None:
    lines.extend(["0", "CIRCLE", "8", layer, "10", f"{x:.6f}", "20", f"{y:.6f}", "30", "0", "40", f"{radius:.6f}"])


def _append_line(lines: list[str], x1: float, y1: float, x2: float, y2: float, layer: str) -> None:
    lines.extend(["0", "LINE", "8", layer, "10", f"{x1:.6f}", "20", f"{y1:.6f}", "30", "0", "11", f"{x2:.6f}", "21", f"{y2:.6f}", "31", "0"])


def _append_slot(lines: list[str], cx: float, cy: float, length: float, width: float, rotation_deg: float) -> None:
    radius = width / 2
    straight = max(0, length - width) / 2
    angle = math.radians(rotation_deg)
    dx = math.cos(angle) * straight
    dy = math.sin(angle) * straight
    _append_circle(lines, cx - dx, cy - dy, radius, layer="OUTLINE")
    _append_circle(lines, cx + dx, cy + dy, radius, layer="OUTLINE")
    normal_x = -math.sin(angle) * radius
    normal_y = math.cos(angle) * radius
    _append_line(lines, cx - dx + normal_x, cy - dy + normal_y, cx + dx + normal_x, cy + dy + normal_y, "OUTLINE")
    _append_line(lines, cx - dx - normal_x, cy - dy - normal_y, cx + dx - normal_x, cy + dy - normal_y, "OUTLINE")
