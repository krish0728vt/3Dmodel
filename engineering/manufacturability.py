from __future__ import annotations

from ai.schemas import (
    BlindHoleOperation,
    CounterboreHoleOperation,
    CountersinkHoleOperation,
    CutExtrudeOperation,
    ElectronicsEnclosureSpec,
    MountingPlateSpec,
    OperationPlan,
    ShellOperation,
    ThroughHoleOperation,
)
from config import CONFIG
from engineering.models import EngineeringWarning, GeometryMetrics, ManufacturingProcess, WarningSeverity


def run_manufacturability_checks(
    structured_spec: object,
    metrics: GeometryMetrics,
    process: ManufacturingProcess,
) -> list[EngineeringWarning]:
    warnings: list[EngineeringWarning] = []
    if process == ManufacturingProcess.THREE_D_PRINTING:
        warnings.extend(_printing_checks(structured_spec, metrics))
    elif process == ManufacturingProcess.CNC_MACHINING:
        warnings.extend(_cnc_checks(structured_spec))
    if not warnings:
        warnings.append(
            EngineeringWarning(
                warning_id="no_rule_warnings",
                severity=WarningSeverity.INFO,
                category="rule_set",
                title="No rule warnings",
                message="No warnings were triggered by the currently implemented advisory rule set.",
            )
        )
    return warnings


def _printing_checks(structured_spec: object, metrics: GeometryMetrics) -> list[EngineeringWarning]:
    warnings: list[EngineeringWarning] = []
    if metrics.size.x_mm > CONFIG.default_printer_x_mm:
        warnings.append(_build_volume_warning("X", metrics.size.x_mm, CONFIG.default_printer_x_mm))
    if metrics.size.y_mm > CONFIG.default_printer_y_mm:
        warnings.append(_build_volume_warning("Y", metrics.size.y_mm, CONFIG.default_printer_y_mm))
    if metrics.size.z_mm > CONFIG.default_printer_z_mm:
        warnings.append(_build_volume_warning("Z", metrics.size.z_mm, CONFIG.default_printer_z_mm))

    for wall in _wall_thicknesses(structured_spec):
        if wall[1] < CONFIG.min_general_print_wall_mm:
            warnings.append(
                EngineeringWarning(
                    warning_id=f"thin_wall_{wall[0]}",
                    severity=WarningSeverity.WARNING,
                    category="3d_printing",
                    title="Thin wall guideline",
                    message=(
                        f"Wall thickness {wall[1]:g} mm is below the configured "
                        f"{CONFIG.min_general_print_wall_mm:g} mm general-purpose printing guideline."
                    ),
                    related_operation_id=wall[0],
                    recommendation="Review wall thickness for the selected material and printer.",
                )
            )
    for hole in _hole_dimensions(structured_spec):
        if hole[1] < CONFIG.small_print_hole_mm:
            warnings.append(
                EngineeringWarning(
                    warning_id=f"small_hole_{hole[0]}",
                    severity=WarningSeverity.INFO,
                    category="3d_printing",
                    title="Small hole",
                    message=f"Hole diameter {hole[1]:g} mm may print undersized on some printers.",
                    related_operation_id=hole[0],
                    recommendation="Consider drilling after printing or increasing clearance.",
                )
            )
    return warnings


def _cnc_checks(structured_spec: object) -> list[EngineeringWarning]:
    warnings: list[EngineeringWarning] = []
    if isinstance(structured_spec, OperationPlan):
        for operation in structured_spec.operations:
            if isinstance(operation, CutExtrudeOperation):
                warnings.append(
                    EngineeringWarning(
                        warning_id=f"internal_corner_{operation.id}",
                        severity=WarningSeverity.INFO,
                        category="cnc_machining",
                        title="Internal sharp corner",
                        message="Rectangular pockets may require tool-radius relief in CNC machining.",
                        related_operation_id=operation.id,
                        recommendation="Add dogbone reliefs or corner radii where mating parts require square corners.",
                    )
                )
            if isinstance(operation, BlindHoleOperation) and operation.depth_mm / operation.hole_diameter_mm > CONFIG.cnc_deep_hole_ratio:
                warnings.append(_deep_hole_warning(operation.id, operation.depth_mm, operation.hole_diameter_mm))
    return warnings


def _wall_thicknesses(structured_spec: object) -> list[tuple[str, float]]:
    values: list[tuple[str, float]] = []
    if isinstance(structured_spec, ElectronicsEnclosureSpec):
        values.append(("electronics_enclosure_wall", structured_spec.wall_thickness_mm))
    if isinstance(structured_spec, MountingPlateSpec):
        values.append(("mounting_plate_thickness", structured_spec.thickness_mm))
    if isinstance(structured_spec, OperationPlan):
        for operation in structured_spec.operations:
            if isinstance(operation, ShellOperation):
                values.append((operation.id, operation.thickness_mm))
    return values


def _hole_dimensions(structured_spec: object) -> list[tuple[str, float]]:
    holes: list[tuple[str, float]] = []
    if isinstance(structured_spec, MountingPlateSpec):
        holes.extend((f"hole_{index}", hole.diameter_mm) for index, hole in enumerate(structured_spec.holes, start=1))
    if isinstance(structured_spec, OperationPlan):
        for operation in structured_spec.operations:
            if isinstance(operation, (ThroughHoleOperation, BlindHoleOperation, CounterboreHoleOperation, CountersinkHoleOperation)):
                holes.append((operation.id, operation.hole_diameter_mm))
    return holes


def _build_volume_warning(axis: str, actual: float, limit: float) -> EngineeringWarning:
    return EngineeringWarning(
        warning_id=f"build_volume_{axis.lower()}",
        severity=WarningSeverity.WARNING,
        category="3d_printing",
        title="Build volume exceeded",
        message=f"Part {axis} extent is {actual:g} mm, above the configured {limit:g} mm build area.",
        recommendation="Reorient, split the part, or configure a larger printer volume.",
    )


def _deep_hole_warning(operation_id: str, depth: float, diameter: float) -> EngineeringWarning:
    return EngineeringWarning(
        warning_id=f"deep_small_hole_{operation_id}",
        severity=WarningSeverity.WARNING,
        category="cnc_machining",
        title="Deep small hole",
        message=f"Hole depth-to-diameter ratio is {depth / diameter:g}, above the configured guideline.",
        related_operation_id=operation_id,
        recommendation="Review drill reach, pecking strategy, and tooling with a machinist.",
    )
