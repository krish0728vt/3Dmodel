from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import cadquery as cq

from ai.schemas import OperationPlan, SupportedPartSpec
from api.schemas import PreviewBoundingBox, PreviewObject, RevisionPreview, SketchPreviewEntity
from cad.generator import generate_workplane
from cad.operation_executor import RegistryObject, execute_operation_plan
from cad.operations import export_stl
from projects.revisions import revision_stl_output_path
from parametrics.resolver import resolved_model


SUBTRACTIVE_OPERATION_TYPES = {
    "cut_hole",
    "cut_extrude",
    "through_hole",
    "blind_hole",
    "counterbore_hole",
    "countersink_hole",
    "rectangular_hole_pattern",
    "circular_hole_pattern",
    "boolean_cut",
}
SKETCH_OPERATION_TYPES = {"create_sketch", "create_sketch_rectangle", "create_sketch_circle"}


def preview_output_dir(project_id: str, revision_number: int) -> Path:
    return Path("outputs") / "projects" / project_id / f"revision_{revision_number:03d}" / "preview"


def preview_metadata_path(project_id: str, revision_number: int) -> Path:
    return Path("outputs") / "projects" / project_id / f"revision_{revision_number:03d}.preview.json"


def preview_mesh_path(project_id: str, revision_number: int, operation_id: str) -> Path:
    return preview_output_dir(project_id, revision_number) / f"{_safe_filename(operation_id)}.stl"


def generate_revision_preview(
    model: SupportedPartSpec | OperationPlan,
    project_id: str,
    revision_number: int,
) -> RevisionPreview:
    """Build semantic preview metadata from deterministic CAD execution."""

    model = resolved_model(model)
    final_mesh_url = f"/api/projects/{project_id}/download/stl?revision={revision_number}"
    if isinstance(model, OperationPlan):
        preview = _operation_plan_preview(model, project_id, revision_number, final_mesh_url)
    else:
        preview = _template_preview(model, project_id, revision_number, final_mesh_url)

    path = preview_metadata_path(project_id, revision_number)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preview.model_dump(mode="json"), indent=2), encoding="utf-8")
    return preview


def _operation_plan_preview(
    plan: OperationPlan,
    project_id: str,
    revision_number: int,
    final_mesh_url: str,
) -> RevisionPreview:
    result = execute_operation_plan(plan)
    objects: list[PreviewObject] = []

    for operation in plan.operations:
        operation_id = operation.id
        registry_object = result.objects.get(operation_id)
        operation_data = operation.model_dump(mode="json")
        operation_type = str(operation_data.get("operation_type", "operation"))
        label = str(operation_data.get("label") or _label_from_id(operation_id))

        if operation_type in SKETCH_OPERATION_TYPES:
            objects.append(_sketch_preview(operation, registry_object))
            continue

        if operation_type in SUBTRACTIVE_OPERATION_TYPES:
            helper = _subtractive_helper(operation, result.objects)
            mesh_url = None
            bbox = _registry_bbox(registry_object)
            if helper is not None:
                mesh_path = preview_mesh_path(project_id, revision_number, operation_id)
                export_stl(helper, mesh_path)
                mesh_url = _mesh_url(project_id, revision_number, operation_id)
                bbox = _bbox_from_workplane(helper)
            objects.append(
                PreviewObject(
                    operation_id=operation_id,
                    label=label,
                    operation_type=operation_type,
                    object_type="subtractive_helper",
                    mesh_url=mesh_url,
                    bounding_box=bbox,
                    visible_by_default=True,
                    selectable=True,
                    source_operation=operation_data,
                    notes="Subtractive features are shown as semantic cutter/helper geometry, not independent final solids.",
                )
            )
            continue

        helper = _additive_helper(operation, result.objects)
        target = helper or (registry_object.workplane if registry_object and registry_object.kind == "solid" else None)
        mesh_url = None
        bbox = None
        if target is not None:
            mesh_path = preview_mesh_path(project_id, revision_number, operation_id)
            export_stl(target, mesh_path)
            mesh_url = _mesh_url(project_id, revision_number, operation_id)
            bbox = _bbox_from_workplane(target)

        objects.append(
            PreviewObject(
                operation_id=operation_id,
                label=label,
                operation_type=operation_type,
                object_type="helper" if helper is not None else "solid",
                mesh_url=mesh_url,
                bounding_box=bbox or _registry_bbox(registry_object),
                visible_by_default=True,
                selectable=True,
                source_operation=operation_data,
            )
        )

    overall = _bbox_from_workplane(result.final_object)
    return RevisionPreview(
        project_id=project_id,
        revision=revision_number,
        final_mesh_url=final_mesh_url,
        objects=objects,
        overall_bounding_box=overall,
        limitations=[
            "Browser preview selection maps to structured operations and helper geometry where possible.",
            "Preview meshes do not expose native STEP/BREP face or edge topology.",
        ],
    )


def _template_preview(
    model: SupportedPartSpec,
    project_id: str,
    revision_number: int,
    final_mesh_url: str,
) -> RevisionPreview:
    workplane = generate_workplane(model)
    bbox = _bbox_from_workplane(workplane)
    part_type = str(model.model_dump(mode="json").get("part_type", "template_part"))
    return RevisionPreview(
        project_id=project_id,
        revision=revision_number,
        final_mesh_url=final_mesh_url,
        objects=[
            PreviewObject(
                operation_id="model",
                label=_label_from_id(part_type),
                operation_type=part_type,
                object_type="final_solid",
                mesh_url=final_mesh_url,
                bounding_box=bbox,
                visible_by_default=True,
                selectable=True,
                source_operation=model.model_dump(mode="json"),
                notes="Template models expose one semantic selectable object.",
            )
        ],
        overall_bounding_box=bbox,
        limitations=[
            "Template preview exposes whole-model selection only.",
            "Browser preview meshes do not expose native STEP/BREP face or edge topology.",
        ],
    )


def _sketch_preview(operation: Any, registry_object: RegistryObject | None) -> PreviewObject:
    data = operation.model_dump(mode="json")
    operation_id = str(data["id"])
    return PreviewObject(
        operation_id=operation_id,
        label=str(data.get("label") or _label_from_id(operation_id)),
        operation_type=str(data.get("operation_type", "sketch")),
        object_type="sketch",
        bounding_box=_registry_bbox(registry_object) or _bbox_from_points(_sketch_points(operation)),
        visible_by_default=False,
        selectable=True,
        source_operation=data,
        sketch_entities=_sketch_entities(operation),
        notes="Sketches are semantic line overlays and are hidden until selected.",
    )


def _additive_helper(operation: Any, objects: dict[str, RegistryObject]) -> cq.Workplane | None:
    data = operation.model_dump(mode="json")
    operation_type = data.get("operation_type")
    target = objects.get(str(data.get("target_id", "")))
    if target is None:
        return None
    bbox = target.workplane.val().BoundingBox()
    if operation_type == "boss":
        height = float(data["height_mm"])
        diameter = float(data["diameter_mm"])
        x, y = data.get("position", [0, 0])
        return cq.Workplane("XY").circle(diameter / 2).extrude(height).translate((x, y, bbox.zmax))
    if operation_type == "rib":
        start = data["start"]
        end = data["end"]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 0:
            return None
        angle = math.degrees(math.atan2(dy, dx))
        center = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        return (
            cq.Workplane("XY")
            .box(length, float(data["thickness_mm"]), float(data["height_mm"]))
            .translate((0, 0, float(data["height_mm"]) / 2))
            .rotate((0, 0, 0), (0, 0, 1), angle)
            .translate((center[0], center[1], bbox.zmax))
        )
    return None


def _subtractive_helper(operation: Any, objects: dict[str, RegistryObject]) -> cq.Workplane | None:
    data = operation.model_dump(mode="json")
    operation_type = data.get("operation_type")
    target = objects.get(str(data.get("target_id", "")))
    bbox = target.workplane.val().BoundingBox() if target is not None else None

    if operation_type in {"cut_hole", "through_hole", "blind_hole", "counterbore_hole", "countersink_hole"} and bbox:
        diameter = float(data.get("diameter_mm") or data.get("hole_diameter_mm") or data.get("counterbore_diameter_mm") or 1)
        depth = float(data.get("depth_mm") or bbox.zlen + 2)
        position = data.get("position", [0, 0])
        return cq.Workplane("XY").circle(diameter / 2).extrude(depth).translate((position[0], position[1], bbox.zmax - depth))

    if operation_type == "cut_extrude":
        sketch = objects.get(str(data.get("sketch_id", "")))
        if sketch is None:
            return None
        distance = data.get("distance_mm")
        if distance is None and bbox is not None:
            distance = max(bbox.xlen, bbox.ylen, bbox.zlen) * 3 + 10
        if distance is None:
            return None
        signed_distance = float(distance) if data.get("direction", "negative") == "positive" else -float(distance)
        return sketch.workplane.extrude(signed_distance)

    if operation_type in {"rectangular_hole_pattern", "circular_hole_pattern"} and bbox:
        diameter = float(data.get("hole_diameter_mm", 1))
        cutters: list[cq.Workplane] = []
        if operation_type == "rectangular_hole_pattern":
            cx, cy = data.get("center", [0, 0])
            count_x = int(data["count_x"])
            count_y = int(data["count_y"])
            sx = float(data["spacing_x_mm"])
            sy = float(data["spacing_y_mm"])
            x0 = cx - sx * (count_x - 1) / 2
            y0 = cy - sy * (count_y - 1) / 2
            positions = [(x0 + ix * sx, y0 + iy * sy) for ix in range(count_x) for iy in range(count_y)]
        else:
            cx, cy = data.get("center", [0, 0])
            radius = float(data["radius_mm"])
            count = int(data["count"])
            start = math.radians(float(data.get("start_angle_deg", 0)))
            positions = [
                (cx + radius * math.cos(start + 2 * math.pi * index / count), cy + radius * math.sin(start + 2 * math.pi * index / count))
                for index in range(count)
            ]
        for x, y in positions:
            cutters.append(cq.Workplane("XY").circle(diameter / 2).extrude(bbox.zlen + 2).translate((x, y, bbox.zmin - 1)))
        result = cutters[0]
        for cutter in cutters[1:]:
            result = result.union(cutter)
        return result

    tool = objects.get(str(data.get("tool_id", "")))
    return tool.workplane if tool is not None and tool.kind == "solid" else None


def _bbox_from_workplane(workplane: cq.Workplane) -> PreviewBoundingBox:
    return _bbox(workplane.val().BoundingBox())


def _registry_bbox(registry_object: RegistryObject | None) -> PreviewBoundingBox | None:
    if registry_object is None:
        return None
    try:
        return _bbox_from_workplane(registry_object.workplane)
    except Exception:
        return None


def _bbox(box: Any) -> PreviewBoundingBox:
    return PreviewBoundingBox(
        xmin=float(box.xmin),
        ymin=float(box.ymin),
        zmin=float(box.zmin),
        xmax=float(box.xmax),
        ymax=float(box.ymax),
        zmax=float(box.zmax),
        xlen=float(box.xlen),
        ylen=float(box.ylen),
        zlen=float(box.zlen),
    )


def _bbox_from_points(points: list[tuple[float, float, float]]) -> PreviewBoundingBox | None:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    zmin, zmax = min(zs), max(zs)
    return PreviewBoundingBox(
        xmin=xmin,
        ymin=ymin,
        zmin=zmin,
        xmax=xmax,
        ymax=ymax,
        zmax=zmax,
        xlen=xmax - xmin,
        ylen=ymax - ymin,
        zlen=zmax - zmin,
    )


def _sketch_entities(operation: Any) -> list[SketchPreviewEntity]:
    data = operation.model_dump(mode="json")
    if data.get("operation_type") == "create_sketch_rectangle":
        width = float(data["width_mm"])
        height = float(data["height_mm"])
        center = data.get("center", [0, 0, 0])
        points = _rectangle_points(width, height, center)
        return [SketchPreviewEntity(entity_type="rectangle", points=points)]
    if data.get("operation_type") == "create_sketch_circle":
        center = data.get("center", [0, 0, 0])
        diameter = float(data["diameter_mm"])
        return [SketchPreviewEntity(entity_type="circle", points=_circle_points(center, diameter))]
    if data.get("operation_type") != "create_sketch":
        return []

    sketch = data["sketch"]
    origin = sketch.get("origin", [0, 0, 0])
    entities: list[SketchPreviewEntity] = []
    for entity in sketch.get("entities", []):
        entity_type = entity.get("entity_type", "entity")
        if entity_type == "rectangle":
            entities.append(SketchPreviewEntity(entity_type=entity_type, points=_rectangle_points(float(entity["width_mm"]), float(entity["height_mm"]), _combine_origin(origin, entity.get("center", [0, 0])))))
        elif entity_type == "circle":
            entities.append(SketchPreviewEntity(entity_type=entity_type, points=_circle_points(_combine_origin(origin, entity.get("center", [0, 0])), float(entity["diameter_mm"]))))
        elif entity_type == "line":
            entities.append(SketchPreviewEntity(entity_type=entity_type, points=[_combine_origin(origin, entity["start"]), _combine_origin(origin, entity["end"])]))
        elif entity_type == "polyline":
            points = [_combine_origin(origin, point) for point in entity.get("points", [])]
            if entity.get("closed") and points:
                points.append(points[0])
            entities.append(SketchPreviewEntity(entity_type=entity_type, points=points))
    return entities


def _sketch_points(operation: Any) -> list[tuple[float, float, float]]:
    return [point for entity in _sketch_entities(operation) for point in entity.points]


def _rectangle_points(width: float, height: float, center: list[float] | tuple[float, ...]) -> list[tuple[float, float, float]]:
    cx, cy, cz = _point3(center)
    half_w = width / 2
    half_h = height / 2
    return [
        (cx - half_w, cy - half_h, cz),
        (cx + half_w, cy - half_h, cz),
        (cx + half_w, cy + half_h, cz),
        (cx - half_w, cy + half_h, cz),
        (cx - half_w, cy - half_h, cz),
    ]


def _circle_points(center: list[float] | tuple[float, ...], diameter: float, segments: int = 48) -> list[tuple[float, float, float]]:
    cx, cy, cz = _point3(center)
    radius = diameter / 2
    return [
        (cx + radius * math.cos(2 * math.pi * index / segments), cy + radius * math.sin(2 * math.pi * index / segments), cz)
        for index in range(segments + 1)
    ]


def _combine_origin(origin: list[float], point: list[float]) -> tuple[float, float, float]:
    return (float(origin[0]) + float(point[0]), float(origin[1]) + float(point[1]), float(origin[2]))


def _point3(value: list[float] | tuple[float, ...]) -> tuple[float, float, float]:
    if len(value) == 2:
        return (float(value[0]), float(value[1]), 0.0)
    return (float(value[0]), float(value[1]), float(value[2]))


def _mesh_url(project_id: str, revision_number: int, operation_id: str) -> str:
    return f"/api/projects/{project_id}/revisions/{revision_number}/preview/{operation_id}/mesh"


def _label_from_id(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "preview"


def ensure_final_stl(model: SupportedPartSpec | OperationPlan, project_id: str, revision_number: int) -> Path:
    path = revision_stl_output_path(project_id, revision_number)
    if not path.exists():
        export_stl(generate_workplane(resolved_model(model)), path)
    return path
