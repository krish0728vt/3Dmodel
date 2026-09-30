from __future__ import annotations

from datetime import UTC, datetime

from ai.schemas import SupportedDesignSpec
from cad.generator import generate_workplane
from engineering.geometry import calculate_geometry_metrics
from engineering.manufacturability import run_manufacturability_checks
from engineering.materials import get_material
from engineering.models import DisplayMetrics, EngineeringReport, ManufacturingProcess, MassEstimate
from engineering.units import display_length


def analyze_part(
    structured_spec: SupportedDesignSpec,
    *,
    project_id: str | None = None,
    revision_number: int | None = None,
    material_id: str | None = None,
    manufacturing_process: ManufacturingProcess | str | None = None,
    display_units: str = "mm",
) -> EngineeringReport:
    part = generate_workplane(structured_spec)
    metrics = calculate_geometry_metrics(part)
    material = get_material(material_id)
    process = (
        manufacturing_process
        if isinstance(manufacturing_process, ManufacturingProcess)
        else ManufacturingProcess(manufacturing_process or ManufacturingProcess.UNKNOWN)
    )
    mass_estimate = None
    if material is not None:
        volume_cm3 = metrics.volume_mm3 / 1000
        mass_g = volume_cm3 * material.density_g_cm3
        mass_estimate = MassEstimate(
            material_id=material.material_id,
            density_g_cm3=material.density_g_cm3,
            volume_cm3=volume_cm3,
            mass_g=mass_g,
            mass_kg=mass_g / 1000,
        )
    length_unit = "in" if display_units in {"in", "inch"} else "mm"
    warnings = run_manufacturability_checks(structured_spec, metrics, process)
    return EngineeringReport(
        project_id=project_id,
        revision_number=revision_number,
        geometry_metrics=metrics,
        display_metrics=DisplayMetrics(
            length_unit=length_unit,
            x=display_length(metrics.size.x_mm, length_unit),
            y=display_length(metrics.size.y_mm, length_unit),
            z=display_length(metrics.size.z_mm, length_unit),
        ),
        material=material,
        mass_estimate=mass_estimate,
        manufacturing_process=process,
        warnings=warnings,
        generated_at=datetime.now(UTC).isoformat(),
    )
