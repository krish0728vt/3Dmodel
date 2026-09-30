from __future__ import annotations

from pydantic import ValidationError

from ai.parser import PromptParserError, UnsupportedPartError
from assemblies.validation import AssemblyValidationError
from cad.operation_executor import OperationExecutionError
from cad.operation_validator import OperationValidationError
from cad.validator import GeometryValidationError
from engineering.geometry import GeometryAnalysisError
from engineering.materials import UnknownMaterialError
from engineering.units import UnitConversionError
from learning.models import FailureCategory
from parametrics.resolver import ParametricResolutionError


def classify_failure(exc: BaseException) -> FailureCategory:
    """Map expected exceptions to stable failure categories."""

    message = str(exc).lower()
    if isinstance(exc, ValidationError):
        return FailureCategory.SCHEMA_ERROR
    if isinstance(exc, UnsupportedPartError):
        return FailureCategory.UNSUPPORTED_PART
    if isinstance(exc, PromptParserError):
        return FailureCategory.PARSER_FAILURE
    if isinstance(exc, ParametricResolutionError):
        if "cycle" in message:
            return FailureCategory.DEPENDENCY_CYCLE
        if "constraint conflict" in message:
            return FailureCategory.CONSTRAINT_CONFLICT
        if "missing parameter" in message:
            return FailureCategory.MISSING_DESIGN_PARAMETER
        return FailureCategory.PARAMETRIC_RESOLUTION_FAILURE
    if isinstance(exc, AssemblyValidationError):
        if "transform" in message or "grounded" in message:
            return FailureCategory.ASSEMBLY_TRANSFORM_FAILURE
        if "interference" in message or "overlap" in message:
            return FailureCategory.ASSEMBLY_INTERFERENCE_FAILURE
        if "export" in message:
            return FailureCategory.ASSEMBLY_EXPORT_FAILURE
        return FailureCategory.ASSEMBLY_REFERENCE_FAILURE
    if isinstance(exc, OperationValidationError):
        if "duplicate" in message:
            return FailureCategory.DUPLICATE_ID
        if "unknown or future" in message:
            return FailureCategory.FORWARD_REFERENCE
        if "references" in message:
            return FailureCategory.INVALID_REFERENCE
        return FailureCategory.INVALID_GEOMETRY
    if isinstance(exc, GeometryValidationError):
        return FailureCategory.INVALID_GEOMETRY
    if isinstance(exc, (GeometryAnalysisError, UnknownMaterialError, UnitConversionError)):
        return FailureCategory.ENGINEERING_ANALYSIS_FAILURE
    if isinstance(exc, OperationExecutionError):
        if "sketch" in message:
            return FailureCategory.SKETCH_FAILURE
        if "loft" in message:
            return FailureCategory.LOFT_FAILURE
        if "sweep" in message:
            return FailureCategory.SWEEP_FAILURE
        if "shell" in message:
            return FailureCategory.SHELL_FAILURE
        if "hole feature" in message or "counterbore" in message or "countersink" in message:
            return FailureCategory.HOLE_FEATURE_FAILURE
        if "boolean" in message:
            return FailureCategory.BOOLEAN_FAILURE
        if "fillet" in message:
            return FailureCategory.FILLET_FAILURE
        if "chamfer" in message:
            return FailureCategory.CHAMFER_FAILURE
        if "pattern" in message:
            return FailureCategory.PATTERN_FAILURE
        if "revolve" in message:
            return FailureCategory.REVOLVE_FAILURE
        if "volume" in message:
            return FailureCategory.ZERO_VOLUME
        return FailureCategory.CAD_KERNEL_FAILURE
    if "export" in message or "step" in message:
        return FailureCategory.EXPORT_FAILURE
    if "boolean" in message:
        return FailureCategory.BOOLEAN_FAILURE
    if "fillet" in message:
        return FailureCategory.FILLET_FAILURE
    if "chamfer" in message:
        return FailureCategory.CHAMFER_FAILURE
    if "pattern" in message:
        return FailureCategory.PATTERN_FAILURE
    if "revolve" in message:
        return FailureCategory.REVOLVE_FAILURE
    if "loft" in message:
        return FailureCategory.LOFT_FAILURE
    if "sweep" in message:
        return FailureCategory.SWEEP_FAILURE
    if "shell" in message:
        return FailureCategory.SHELL_FAILURE
    if "hole feature" in message or "counterbore" in message or "countersink" in message:
        return FailureCategory.HOLE_FEATURE_FAILURE
    return FailureCategory.UNKNOWN_FAILURE
