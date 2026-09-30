from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cadquery as cq

from cad.operations import export_step, export_stl
from capabilities.models import CapabilityManifest, GeometryCapabilityResult, ProviderType, TrustLevel


INPUT_SCHEMA = {
    "type": "object",
    "required": ["module_mm", "teeth", "thickness_mm", "bore_diameter_mm"],
    "properties": {
        "module_mm": {"type": "number", "minimum": 0.2},
        "teeth": {"type": "integer", "minimum": 8, "maximum": 200},
        "thickness_mm": {"type": "number", "minimum": 0.5},
        "bore_diameter_mm": {"type": "number", "minimum": 0},
        "pressure_angle_deg": {"type": "number", "minimum": 14.5, "maximum": 25},
    },
}

OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["result_type", "step_path", "stl_path", "units", "metadata"],
    "properties": {
        "result_type": {"type": "string"},
        "step_path": {"type": "string"},
        "stl_path": {"type": "string"},
        "units": {"type": "string"},
        "metadata": {"type": "object"},
    },
}


def get_manifest() -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="local.spur_gear_generator",
        name="Spur Gear Generator",
        version="1.0.0",
        description="Deterministic local CadQuery spur gear generator using an approximated involute tooth outline.",
        provider_type=ProviderType.LOCAL_ADAPTER,
        source="capabilities.adapters.spur_gear",
        supported_operations=["spur_gear", "gear_generation"],
        required_dependencies=["cadquery"],
        trust_level=TrustLevel.EXPERIMENTAL,
        input_schema=INPUT_SCHEMA,
        output_schema=OUTPUT_SCHEMA,
        output_type="geometry",
        local_adapter="spur_gear_generator",
        risk_notes="Approximated gear tooth geometry for CAD layout; verify critical gears with dedicated gear design software.",
    )


def run_self_test() -> bool:
    result = invoke(
        {
            "module_mm": 1.0,
            "teeth": 24,
            "thickness_mm": 5.0,
            "bore_diameter_mm": 4.0,
            "pressure_angle_deg": 20.0,
        },
        output_dir=Path("outputs") / "capabilities" / "self_test",
    )
    return bool(result.step_path and Path(result.step_path).exists() and result.stl_path and Path(result.stl_path).exists())


def invoke(arguments: dict[str, Any], *, output_dir: str | Path | None = None) -> GeometryCapabilityResult:
    module_mm = float(arguments["module_mm"])
    teeth = int(arguments["teeth"])
    thickness_mm = float(arguments["thickness_mm"])
    bore_diameter_mm = float(arguments["bore_diameter_mm"])
    pressure_angle_deg = float(arguments.get("pressure_angle_deg", 20.0))
    _validate(module_mm, teeth, thickness_mm, bore_diameter_mm, pressure_angle_deg)

    gear = build_spur_gear(
        module_mm=module_mm,
        teeth=teeth,
        thickness_mm=thickness_mm,
        bore_diameter_mm=bore_diameter_mm,
    )
    out_dir = Path(output_dir) if output_dir is not None else Path("outputs") / "capabilities" / "spur_gear"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"spur_gear_m{_tag(module_mm)}_t{teeth}_w{_tag(thickness_mm)}_b{_tag(bore_diameter_mm)}"
    step_path = export_step(gear, out_dir / f"{stem}.step")
    stl_path = export_stl(gear, out_dir / f"{stem}.stl")
    return GeometryCapabilityResult(
        step_path=str(step_path),
        stl_path=str(stl_path),
        metadata={
            "module_mm": module_mm,
            "teeth": teeth,
            "thickness_mm": thickness_mm,
            "bore_diameter_mm": bore_diameter_mm,
            "pitch_diameter_mm": module_mm * teeth,
            "outside_diameter_mm": module_mm * (teeth + 2),
            "root_diameter_mm": max(module_mm * teeth - 2.5 * module_mm, module_mm),
            "pressure_angle_deg": pressure_angle_deg,
            "tooth_profile": "approximated_involute_layout",
        },
    )


def build_spur_gear(
    *,
    module_mm: float,
    teeth: int,
    thickness_mm: float,
    bore_diameter_mm: float,
) -> cq.Workplane:
    pitch_radius = module_mm * teeth / 2
    outer_radius = module_mm * (teeth + 2) / 2
    root_radius = max(pitch_radius - 1.25 * module_mm, module_mm / 2)
    tooth_half_angle = math.pi / teeth * 0.42
    valley_half_angle = math.pi / teeth * 0.24

    points: list[tuple[float, float]] = []
    for index in range(teeth):
        center = 2 * math.pi * index / teeth
        for angle, radius in [
            (center - math.pi / teeth + valley_half_angle, root_radius),
            (center - tooth_half_angle, pitch_radius),
            (center - tooth_half_angle * 0.38, outer_radius),
            (center + tooth_half_angle * 0.38, outer_radius),
            (center + tooth_half_angle, pitch_radius),
            (center + math.pi / teeth - valley_half_angle, root_radius),
        ]:
            points.append((radius * math.cos(angle), radius * math.sin(angle)))

    gear = cq.Workplane("XY").polyline(points).close().extrude(thickness_mm)
    if bore_diameter_mm > 0:
        gear = gear.faces(">Z").workplane().hole(bore_diameter_mm)
    return cq.Workplane("XY").newObject([gear.val()])


def _validate(module_mm: float, teeth: int, thickness_mm: float, bore_diameter_mm: float, pressure_angle_deg: float) -> None:
    if module_mm <= 0:
        raise ValueError("module_mm must be positive.")
    if teeth < 8:
        raise ValueError("teeth must be at least 8.")
    if thickness_mm <= 0:
        raise ValueError("thickness_mm must be positive.")
    pitch_diameter = module_mm * teeth
    root_diameter = max(pitch_diameter - 2.5 * module_mm, module_mm)
    if bore_diameter_mm < 0:
        raise ValueError("bore_diameter_mm must be non-negative.")
    if bore_diameter_mm >= root_diameter * 0.82:
        raise ValueError("bore_diameter_mm is too large for the generated gear root diameter.")
    if pressure_angle_deg <= 0:
        raise ValueError("pressure_angle_deg must be positive.")


def _tag(value: float) -> str:
    return str(value).replace(".", "p")
