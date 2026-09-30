from __future__ import annotations

import struct
from pathlib import Path

import cadquery as cq

from cad.operations import export_stl
from exports.models import StlQuality


QUALITY_SETTINGS: dict[StlQuality, tuple[float, float]] = {
    StlQuality.DRAFT: (0.35, 0.35),
    StlQuality.STANDARD: (0.1, 0.1),
    StlQuality.HIGH: (0.035, 0.035),
}


def export_stl_file(part: cq.Workplane, path: Path, quality: StlQuality) -> Path:
    tolerance, angular_tolerance = QUALITY_SETTINGS[quality]
    return export_stl(part, path, tolerance=tolerance, angular_tolerance=angular_tolerance)


def stl_metadata(path: Path, bbox: dict[str, float] | None = None) -> dict[str, object]:
    triangle_count = _triangle_count(path)
    data: dict[str, object] = {"triangle_count": triangle_count, "file_size_bytes": path.stat().st_size}
    if bbox is not None:
        data["bounding_box_mm"] = bbox
    return data


def _triangle_count(path: Path) -> int | None:
    data = path.read_bytes()
    if len(data) >= 84:
        count = struct.unpack("<I", data[80:84])[0]
        if len(data) == 84 + count * 50:
            return int(count)
    try:
        text = data.decode("utf-8", errors="ignore").lower()
    except Exception:
        return None
    return text.count("facet normal") or None
