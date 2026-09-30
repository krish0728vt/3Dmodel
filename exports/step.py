from __future__ import annotations

from pathlib import Path

import cadquery as cq

from cad.operations import export_step
from engineering.geometry import calculate_geometry_metrics


def export_step_file(part: cq.Workplane, path: Path) -> Path:
    return export_step(part, path)


def validate_step_round_trip(source_part: cq.Workplane, path: Path, *, rel_tol: float = 0.02, abs_tol: float = 0.05) -> dict[str, float]:
    imported = cq.importers.importStep(str(path))
    original = calculate_geometry_metrics(source_part)
    round_tripped = calculate_geometry_metrics(imported)
    _assert_close("volume_mm3", original.volume_mm3, round_tripped.volume_mm3, rel_tol, abs_tol)
    _assert_close("xlen", original.size.x_mm, round_tripped.size.x_mm, rel_tol, abs_tol)
    _assert_close("ylen", original.size.y_mm, round_tripped.size.y_mm, rel_tol, abs_tol)
    _assert_close("zlen", original.size.z_mm, round_tripped.size.z_mm, rel_tol, abs_tol)
    return {
        "original_volume_mm3": original.volume_mm3,
        "round_trip_volume_mm3": round_tripped.volume_mm3,
        "original_x_mm": original.size.x_mm,
        "round_trip_x_mm": round_tripped.size.x_mm,
        "original_y_mm": original.size.y_mm,
        "round_trip_y_mm": round_tripped.size.y_mm,
        "original_z_mm": original.size.z_mm,
        "round_trip_z_mm": round_tripped.size.z_mm,
    }


def _assert_close(label: str, expected: float, actual: float, rel_tol: float, abs_tol: float) -> None:
    tolerance = max(abs_tol, abs(expected) * rel_tol)
    if abs(expected - actual) > tolerance:
        raise ValueError(f"STEP round-trip {label} changed too much: expected {expected:g}, got {actual:g}.")
