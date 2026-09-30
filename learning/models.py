from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceStatus(str, Enum):
    OBSERVED = "OBSERVED"
    VALIDATED = "VALIDATED"
    TRUSTED = "TRUSTED"
    DEPRECATED = "DEPRECATED"
    NEEDS_REVALIDATION = "NEEDS_REVALIDATION"


class FailureCategory(str, Enum):
    SCHEMA_ERROR = "schema_error"
    MISSING_PARAMETER = "missing_parameter"
    UNSUPPORTED_PART = "unsupported_part"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    INVALID_REFERENCE = "invalid_reference"
    DUPLICATE_ID = "duplicate_id"
    FORWARD_REFERENCE = "forward_reference"
    INVALID_GEOMETRY = "invalid_geometry"
    ZERO_VOLUME = "zero_volume"
    BOOLEAN_FAILURE = "boolean_failure"
    FILLET_FAILURE = "fillet_failure"
    CHAMFER_FAILURE = "chamfer_failure"
    PATTERN_FAILURE = "pattern_failure"
    REVOLVE_FAILURE = "revolve_failure"
    SKETCH_FAILURE = "sketch_failure"
    LOFT_FAILURE = "loft_failure"
    SWEEP_FAILURE = "sweep_failure"
    SHELL_FAILURE = "shell_failure"
    HOLE_FEATURE_FAILURE = "hole_feature_failure"
    ENGINEERING_ANALYSIS_FAILURE = "engineering_analysis_failure"
    PARAMETRIC_RESOLUTION_FAILURE = "parametric_resolution_failure"
    DEPENDENCY_CYCLE = "dependency_cycle"
    CONSTRAINT_CONFLICT = "constraint_conflict"
    MISSING_DESIGN_PARAMETER = "missing_design_parameter"
    ASSEMBLY_REFERENCE_FAILURE = "assembly_reference_failure"
    ASSEMBLY_TRANSFORM_FAILURE = "assembly_transform_failure"
    ASSEMBLY_INTERFERENCE_FAILURE = "assembly_interference_failure"
    ASSEMBLY_EXPORT_FAILURE = "assembly_export_failure"
    CAPABILITY = "capability"
    EXPORT_FAILURE = "export_failure"
    PARSER_FAILURE = "parser_failure"
    CAD_KERNEL_FAILURE = "cad_kernel_failure"
    UNKNOWN_FAILURE = "unknown_failure"


class FailureRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    failure_id: str
    timestamp: str
    prompt: str | None = None
    parsed_spec_json: str | None = None
    operation_plan_json: str | None = None
    failing_operation_id: str | None = None
    error_category: FailureCategory
    error_message: str
    relevant_parameters_json: str | None = None
    repair_attempt_count: int = 0
    resolved: bool = False
    successful_repair_id: str | None = None
    normalized_signature: str | None = None


class LessonRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson_id: str
    title: str
    description: str
    problem_signature: str
    applicable_part_types: list[str] = Field(default_factory=list)
    applicable_operation_types: list[str] = Field(default_factory=list)
    known_bad_pattern: str | None = None
    recommended_pattern: str | None = None
    evidence_count: int = 1
    success_count: int = 0
    failure_count: int = 0
    confidence: float = 0.1
    created_at: str
    status: EvidenceStatus = EvidenceStatus.OBSERVED
    confidence_score: float = 0.1
    last_used_at: str | None = None
    last_verified_at: str | None = None
    source_capability_versions: dict[str, str] = Field(default_factory=dict)
    source_engine_version: str | None = None
    contradiction_count: int = 0
    superseded_by_lesson_id: str | None = None
    source_type: str = "manual_entry"
    source_ids: list[str] = Field(default_factory=list)
    regression_ids: list[str] = Field(default_factory=list)
    manually_overridden: bool = False


class SuccessfulPatternRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_id: str
    name: str
    description: str
    applicable_operation_types: list[str] = Field(default_factory=list)
    operation_signature: str | None = None
    part_type: str | None = None
    input_signature: str
    plan_fragment_json: str
    validation_notes: str | None = None
    usage_count: int = 1
    success_count: int = 1
    failure_count: int = 0
    confidence_score: float = 0.1
    status: EvidenceStatus = EvidenceStatus.OBSERVED
    created_at: str | None = None
    last_used_at: str | None = None
    last_verified_at: str | None = None
    source_capabilities: dict[str, str] = Field(default_factory=dict)
    regression_ids: list[str] = Field(default_factory=list)
    manually_overridden: bool = False
    last_success_at: str


class RepairAttemptRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repair_id: str
    failure_id: str
    attempt_number: int
    repaired_plan_json: str | None = None
    strategy: str
    result: str
    error_message: str | None = None
    timestamp: str
    strategy_signature: str | None = None


class RepairStrategyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_signature: str
    problem_signature: str
    strategy: str
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    confidence_score: float = 0.1
    status: EvidenceStatus = EvidenceStatus.OBSERVED
    created_at: str
    last_used_at: str | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None


class AdaptiveLearningStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_failures: int
    resolved_failures: int
    unresolved_failures: int
    lessons_by_status: dict[str, int]
    patterns_by_status: dict[str, int]
    average_lesson_confidence: float
    repair_success_rate: float
    top_failure_categories: list[dict[str, Any]]
