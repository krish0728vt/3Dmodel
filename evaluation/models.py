from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from evaluation.categories import BenchmarkCategory


BENCHMARK_SCHEMA_VERSION = "1.0"


class BenchmarkDifficulty(StrEnum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"
    ADVANCED = "advanced"


class BenchmarkMode(StrEnum):
    TEMPLATE = "template"
    OPERATION_PLAN = "operation_plan"
    PARAMETRIC = "parametric"
    ASSEMBLY = "assembly"
    CAPABILITY = "capability"
    EDIT = "edit"
    ENGINEERING = "engineering"


class BenchmarkStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNSUPPORTED = "unsupported"
    SKIPPED = "skipped"


class FailureCategory(StrEnum):
    PARSER = "parser"
    SCHEMA_VALIDATION = "schema_validation"
    PARAMETRIC_RESOLUTION = "parametric_resolution"
    CAD_VALIDATION = "cad_validation"
    CAD_GENERATION = "cad_generation"
    SOLID_VALIDATION = "solid_validation"
    EXPORT_FAILURE = "export_failure"
    ENGINEERING_FAILURE = "engineering_failure"
    STRUCTURE_MISMATCH = "structure_mismatch"
    GEOMETRY_MISMATCH = "geometry_mismatch"
    ASSEMBLY_FAILURE = "assembly_failure"
    CAPABILITY_FAILURE = "capability_failure"
    REPAIR_FAILURE = "repair_failure"
    EXPECTED_UNSUPPORTED = "expected_unsupported"
    EXPECTED_AMBIGUITY = "expected_ambiguity"


class StageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    success: bool
    skipped: bool = False
    duration_ms: int = 0
    message: str | None = None


class StructuralExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_type: str | None = None
    operation_types: list[str] = Field(default_factory=list)
    min_operation_count: int | None = None
    parameters: dict[str, float] = Field(default_factory=dict)
    relationships: list[str] = Field(default_factory=list)


class GeometricExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bbox: dict[str, float] = Field(default_factory=dict)
    bbox_tolerance_mm: float = 0.35
    volume_min_mm3: float | None = None
    volume_max_mm3: float | None = None
    solid_count: int | None = None


class EngineeringExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str | None = None
    mass_min_g: float | None = None
    mass_max_g: float | None = None
    display_units: str = "mm"
    expected_warning_categories: list[str] = Field(default_factory=list)


class AssemblyFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    components: list[dict[str, Any]]
    expect_interference: bool | None = None


class CapabilityFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str = "local.spur_gear_generator"
    arguments: dict[str, Any]
    expect_success: bool = True
    enable_before_invoke: bool = True


class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_schema_version: str = BENCHMARK_SCHEMA_VERSION
    case_id: str
    name: str
    category: BenchmarkCategory
    difficulty: BenchmarkDifficulty
    prompt: str
    mode: BenchmarkMode
    expected_part_type: str | None = None
    expected_operation_types: list[str] = Field(default_factory=list)
    expected_features: list[str] = Field(default_factory=list)
    expected_parameters: dict[str, float] = Field(default_factory=dict)
    expected_relationships: list[str] = Field(default_factory=list)
    expected_capabilities: list[str] = Field(default_factory=list)
    expected_export_formats: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    fixture_spec: dict[str, Any] | None = None
    repair_fixture_spec: dict[str, Any] | None = None
    assembly_fixture: AssemblyFixture | None = None
    capability_fixture: CapabilityFixture | None = None
    structural_expectation: StructuralExpectation = Field(default_factory=StructuralExpectation)
    geometric_expectation: GeometricExpectation = Field(default_factory=GeometricExpectation)
    engineering_expectation: EngineeringExpectation = Field(default_factory=EngineeringExpectation)
    expected_status: BenchmarkStatus = BenchmarkStatus.PASS
    expected_failure_category: FailureCategory | None = None
    smoke: bool = True


class BenchmarkResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    name: str
    category: BenchmarkCategory
    difficulty: BenchmarkDifficulty
    mode: BenchmarkMode
    started_at: str
    duration_ms: int
    parse_success: bool = False
    schema_validation_success: bool = False
    parametric_resolution_success: bool = False
    cad_validation_success: bool = False
    cad_generation_success: bool = False
    solid_validation_success: bool = False
    step_export_success: bool = False
    stl_export_success: bool = False
    expected_structure_match: bool = False
    engineering_analysis_success: bool = False
    repair_attempted: bool = False
    repair_success: bool = False
    failure_category: FailureCategory | None = None
    failure_message: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    stages: list[StageResult] = Field(default_factory=list)
    overall_status: BenchmarkStatus


class EvaluationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_cases: int
    pass_count: int
    fail_count: int
    unsupported_count: int
    skipped_count: int
    parse_success_rate: float
    schema_success_rate: float
    cad_generation_success_rate: float
    step_export_success_rate: float
    stl_export_success_rate: float
    repair_success_rate: float
    parametric_preservation_rate: float
    assembly_success_rate: float
    capability_success_rate: float
    category: dict[str, dict[str, Any]]
    difficulty: dict[str, dict[str, Any]]
    failure_distribution: dict[str, int]
    total_duration_ms: int
    average_duration_ms: float
    slowest_cases: list[dict[str, Any]]


class RegressionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    previous_status: BenchmarkStatus | None
    current_status: BenchmarkStatus
    regression_type: str
    message: str


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_schema_version: str = BENCHMARK_SCHEMA_VERSION
    suite: str
    milestone: str = "17"
    generated_at: str
    deterministic: bool = True
    live_ai: bool = False
    case_count: int
    filters: dict[str, Any] = Field(default_factory=dict)
    metrics: EvaluationMetrics
    regressions: list[RegressionRecord] = Field(default_factory=list)
    results: list[BenchmarkResult]
