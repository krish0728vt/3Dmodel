from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ManufacturingProcess(str, Enum):
    UNKNOWN = "unknown"
    THREE_D_PRINTING = "3d_printing"
    CNC_MACHINING = "cnc_machining"


class WarningSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class BoundingBoxMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_x_mm: float
    min_y_mm: float
    min_z_mm: float
    max_x_mm: float
    max_y_mm: float
    max_z_mm: float


class SizeMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x_mm: float
    y_mm: float
    z_mm: float


class PointMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x_mm: float
    y_mm: float
    z_mm: float


class GeometryMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    volume_mm3: float
    surface_area_mm2: float
    bounding_box: BoundingBoxMetrics
    size: SizeMetrics
    center_of_mass: PointMetrics
    solid_count: int
    valid: bool = True


class MaterialSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str
    display_name: str
    category: str
    density_g_cm3: float
    notes: str | None = None


class MaterialAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str | None = None


class MassEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str
    density_g_cm3: float
    volume_cm3: float
    mass_g: float
    mass_kg: float
    estimate_basis: str = "solid_geometry_full_density"


class EngineeringWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warning_id: str
    severity: WarningSeverity
    category: str
    title: str
    message: str
    related_operation_id: str | None = None
    recommendation: str | None = None


class DisplayMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length_unit: Literal["mm", "in"]
    x: float
    y: float
    z: float


class EngineeringReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str | None = None
    revision_number: int | None = None
    geometry_metrics: GeometryMetrics
    display_metrics: DisplayMetrics
    material: MaterialSpec | None = None
    mass_estimate: MassEstimate | None = None
    manufacturing_process: ManufacturingProcess = ManufacturingProcess.UNKNOWN
    warnings: list[EngineeringWarning]
    generated_at: str
