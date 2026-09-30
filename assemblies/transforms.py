from __future__ import annotations

import math
from itertools import product

import cadquery as cq

from assemblies.models import BoundingBox, Transform


def apply_transform(part: cq.Workplane, transform: Transform) -> cq.Workplane:
    result = part
    if transform.rotation_x_deg:
        result = result.rotate((0, 0, 0), (1, 0, 0), transform.rotation_x_deg)
    if transform.rotation_y_deg:
        result = result.rotate((0, 0, 0), (0, 1, 0), transform.rotation_y_deg)
    if transform.rotation_z_deg:
        result = result.rotate((0, 0, 0), (0, 0, 1), transform.rotation_z_deg)
    return result.translate((transform.translation_x_mm, transform.translation_y_mm, transform.translation_z_mm))


def transform_point(point: tuple[float, float, float], transform: Transform) -> tuple[float, float, float]:
    x, y, z = point
    x, y, z = _rotate_x(x, y, z, transform.rotation_x_deg)
    x, y, z = _rotate_y(x, y, z, transform.rotation_y_deg)
    x, y, z = _rotate_z(x, y, z, transform.rotation_z_deg)
    return (x + transform.translation_x_mm, y + transform.translation_y_mm, z + transform.translation_z_mm)


def transform_bounding_box(box: BoundingBox, transform: Transform) -> BoundingBox:
    corners = [
        transform_point((x, y, z), transform)
        for x, y, z in product([box.xmin, box.xmax], [box.ymin, box.ymax], [box.zmin, box.zmax])
    ]
    return bounding_box_from_points(corners)


def bounding_box_from_points(points: list[tuple[float, float, float]]) -> BoundingBox:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    zmin, zmax = min(zs), max(zs)
    return BoundingBox(xmin=xmin, ymin=ymin, zmin=zmin, xmax=xmax, ymax=ymax, zmax=zmax, xlen=xmax - xmin, ylen=ymax - ymin, zlen=zmax - zmin)


def merge_bounding_boxes(boxes: list[BoundingBox]) -> BoundingBox | None:
    if not boxes:
        return None
    return bounding_box_from_points([(box.xmin, box.ymin, box.zmin) for box in boxes] + [(box.xmax, box.ymax, box.zmax) for box in boxes])


def boxes_overlap(first: BoundingBox, second: BoundingBox) -> bool:
    return not (
        first.xmax <= second.xmin
        or first.xmin >= second.xmax
        or first.ymax <= second.ymin
        or first.ymin >= second.ymax
        or first.zmax <= second.zmin
        or first.zmin >= second.zmax
    )


def bbox_from_cadquery(part: cq.Workplane) -> BoundingBox:
    box = part.val().BoundingBox()
    return BoundingBox(
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


def _rotate_x(x: float, y: float, z: float, degrees: float) -> tuple[float, float, float]:
    radians = math.radians(degrees)
    cos_v = math.cos(radians)
    sin_v = math.sin(radians)
    return (x, y * cos_v - z * sin_v, y * sin_v + z * cos_v)


def _rotate_y(x: float, y: float, z: float, degrees: float) -> tuple[float, float, float]:
    radians = math.radians(degrees)
    cos_v = math.cos(radians)
    sin_v = math.sin(radians)
    return (x * cos_v + z * sin_v, y, -x * sin_v + z * cos_v)


def _rotate_z(x: float, y: float, z: float, degrees: float) -> tuple[float, float, float]:
    radians = math.radians(degrees)
    cos_v = math.cos(radians)
    sin_v = math.sin(radians)
    return (x * cos_v - y * sin_v, x * sin_v + y * cos_v, z)
