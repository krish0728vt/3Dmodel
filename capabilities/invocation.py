from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any

from capabilities.models import CapabilityErrorCategory, CapabilityInvokeResponse, CapabilityRecord, ProviderType, TrustLevel, ValidationStatus
from capabilities.registry import CapabilityRegistry
from config import CONFIG
from learning.models import FailureCategory
from learning.store import LearningStore


class CapabilityInvocationError(RuntimeError):
    def __init__(self, category: CapabilityErrorCategory, message: str) -> None:
        super().__init__(message)
        self.category = category


def invoke_capability(
    capability_id: str,
    arguments: dict[str, Any],
    *,
    registry: CapabilityRegistry | None = None,
    learning_store: LearningStore | None = None,
) -> CapabilityInvokeResponse:
    registry = registry or CapabilityRegistry()
    record = registry.get(capability_id)
    started = time.perf_counter()
    try:
        if record is None:
            raise CapabilityInvocationError(CapabilityErrorCategory.PERMISSION_FAILURE, f"Unknown capability: {capability_id}")
        _check_invocation_allowed(record)
        _validate_schema(arguments, record.input_schema, "input")
        result = _invoke_with_timeout(record, arguments)
        _validate_schema(result, record.output_schema, "output")
        duration_ms = int((time.perf_counter() - started) * 1000)
        registry.record_invocation(capability_id, success=True)
        _record_learning(learning_store, record, "success", None, duration_ms)
        return CapabilityInvokeResponse(capability_id=capability_id, result=result, duration_ms=duration_ms)
    except CapabilityInvocationError as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        if record is not None:
            registry.record_invocation(capability_id, success=False)
            _record_learning(learning_store, record, "failure", exc.category, duration_ms)
        raise
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        if record is not None:
            registry.record_invocation(capability_id, success=False)
            _record_learning(learning_store, record, "failure", CapabilityErrorCategory.EXECUTION_FAILURE, duration_ms)
        raise CapabilityInvocationError(CapabilityErrorCategory.EXECUTION_FAILURE, str(exc)) from exc


def _check_invocation_allowed(record: CapabilityRecord) -> None:
    if not record.enabled:
        raise CapabilityInvocationError(CapabilityErrorCategory.PERMISSION_FAILURE, "Capability is disabled.")
    if record.trust_level not in {TrustLevel.CORE, TrustLevel.APPROVED}:
        raise CapabilityInvocationError(CapabilityErrorCategory.PERMISSION_FAILURE, "Capability is not approved for normal use.")
    if record.validation_status != ValidationStatus.PASSED:
        raise CapabilityInvocationError(CapabilityErrorCategory.PERMISSION_FAILURE, "Capability must pass self-test before invocation.")


def _invoke_with_timeout(record: CapabilityRecord, arguments: dict[str, Any]) -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_invoke_adapter, record, arguments)
        try:
            return future.result(timeout=CONFIG.capability_call_timeout_seconds)
        except FutureTimeout as exc:
            raise CapabilityInvocationError(CapabilityErrorCategory.TIMEOUT, "Capability invocation timed out.") from exc


def _invoke_adapter(record: CapabilityRecord, arguments: dict[str, Any]) -> dict[str, Any]:
    if record.provider_type == ProviderType.LOCAL_ADAPTER and record.local_adapter == "spur_gear_generator":
        from capabilities.adapters.spur_gear import invoke

        return invoke(arguments).model_dump(mode="json")
    if record.provider_type == ProviderType.HTTP_API:
        from capabilities.http import invoke_http_capability

        return invoke_http_capability(record, arguments)
    raise CapabilityInvocationError(
        CapabilityErrorCategory.EXECUTION_FAILURE,
        f"No invocation adapter is configured for provider type {record.provider_type}.",
    )


def _validate_schema(value: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    if not schema:
        return
    if schema.get("type") not in {None, "object"}:
        raise CapabilityInvocationError(CapabilityErrorCategory.SCHEMA_FAILURE, f"{label} schema must be an object schema.")
    required = schema.get("required", [])
    for field in required:
        if field not in value:
            raise CapabilityInvocationError(CapabilityErrorCategory.SCHEMA_FAILURE, f"Missing required {label} field: {field}")
    properties = schema.get("properties", {})
    for field, field_schema in properties.items():
        if field in value:
            _validate_field(field, value[field], field_schema, label)


def _validate_field(field: str, value: Any, field_schema: dict[str, Any], label: str) -> None:
    expected = field_schema.get("type")
    if expected == "number" and not isinstance(value, (int, float)):
        raise CapabilityInvocationError(CapabilityErrorCategory.SCHEMA_FAILURE, f"{label}.{field} must be a number.")
    if expected == "integer" and not isinstance(value, int):
        raise CapabilityInvocationError(CapabilityErrorCategory.SCHEMA_FAILURE, f"{label}.{field} must be an integer.")
    if expected == "string" and not isinstance(value, str):
        raise CapabilityInvocationError(CapabilityErrorCategory.SCHEMA_FAILURE, f"{label}.{field} must be a string.")
    if expected == "object" and not isinstance(value, dict):
        raise CapabilityInvocationError(CapabilityErrorCategory.SCHEMA_FAILURE, f"{label}.{field} must be an object.")
    if isinstance(value, (int, float)):
        minimum = field_schema.get("minimum")
        maximum = field_schema.get("maximum")
        if minimum is not None and value < minimum:
            raise CapabilityInvocationError(CapabilityErrorCategory.SCHEMA_FAILURE, f"{label}.{field} is below minimum.")
        if maximum is not None and value > maximum:
            raise CapabilityInvocationError(CapabilityErrorCategory.SCHEMA_FAILURE, f"{label}.{field} is above maximum.")


def _record_learning(
    learning_store: LearningStore | None,
    record: CapabilityRecord,
    status: str,
    category: CapabilityErrorCategory | None,
    duration_ms: int,
) -> None:
    if learning_store is None:
        return
    if status == "failure":
        learning_store.record_failure(
            error_category=FailureCategory.CAPABILITY,
            error_message=f"{record.capability_id} failed with {category.value if category else 'unknown'}",
            relevant_parameters={"capability_id": record.capability_id, "duration_ms": duration_ms},
        )
    else:
        learning_store.record_successful_pattern(
            name=f"Capability success: {record.capability_id}",
            description=f"{record.name} completed in {duration_ms} ms.",
            applicable_operation_types=record.supported_operations,
            input_signature=json.dumps({"capability_id": record.capability_id}),
            plan_fragment_json="{}",
            validation_notes="Recorded capability invocation success; trust level unchanged.",
        )
