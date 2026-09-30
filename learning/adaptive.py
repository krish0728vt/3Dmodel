from __future__ import annotations

import json
import platform
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from ai.schemas import OperationPlan
from config import CONFIG
from learning.models import EvidenceStatus


ENGINE_SCHEMA_VERSION = "1.2"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def environment_context(capability_versions: dict[str, str] | None = None) -> dict[str, Any]:
    cadquery_version = "unknown"
    occ_version = "unknown"
    try:
        import cadquery as cq

        cadquery_version = getattr(cq, "__version__", "unknown")
        occ_version = getattr(getattr(cq, "occ_impl", None), "__version__", "unknown")
    except Exception:
        pass
    return {
        "python_version": platform.python_version(),
        "cadquery_version": cadquery_version,
        "opencascade_version": occ_version,
        "shah_schema_version": ENGINE_SCHEMA_VERSION,
        "capability_versions": capability_versions or {},
    }


def calculate_confidence(
    *,
    success_count: int,
    failure_count: int = 0,
    contradiction_count: int = 0,
    compatible_version: bool = True,
    diversity_count: int = 1,
) -> float:
    total = max(success_count + failure_count + contradiction_count, 0)
    evidence = min(success_count, 10) * 0.07
    ratio = (success_count / total) * 0.4 if total else 0.0
    diversity = min(max(diversity_count, 1), 5) * 0.02
    penalty = min(failure_count * 0.06 + contradiction_count * 0.12, 0.6)
    version_penalty = 0.0 if compatible_version else 0.18
    confidence = 0.1 + evidence + ratio + diversity - penalty - version_penalty
    return round(max(0.0, min(confidence, 0.99)), 3)


def promote_status(
    *,
    success_count: int,
    failure_count: int = 0,
    contradiction_count: int = 0,
    manually_overridden: bool = False,
    current_status: EvidenceStatus | str = EvidenceStatus.OBSERVED,
) -> EvidenceStatus:
    current = EvidenceStatus(current_status)
    if current == EvidenceStatus.DEPRECATED:
        return current
    if manually_overridden:
        return current
    total = max(success_count + failure_count, 1)
    success_ratio = success_count / total
    if contradiction_count >= CONFIG.lesson_deprecate_contradictions:
        return EvidenceStatus.DEPRECATED
    if contradiction_count >= 2 and current == EvidenceStatus.TRUSTED:
        return EvidenceStatus.VALIDATED
    if success_count >= CONFIG.lesson_trusted_successes and success_ratio >= 0.85 and contradiction_count == 0:
        return EvidenceStatus.TRUSTED
    if success_count >= CONFIG.lesson_validated_successes and success_ratio >= 0.7:
        return EvidenceStatus.VALIDATED
    return EvidenceStatus.OBSERVED


def explain_confidence(
    *,
    success_count: int,
    failure_count: int,
    contradiction_count: int,
    compatible_version: bool = True,
) -> list[str]:
    return [
        f"{success_count} successful confirmations",
        f"{failure_count} failures",
        f"{contradiction_count} contradictions",
        "current engine version compatible" if compatible_version else "engine or capability version needs revalidation",
    ]


def normalize_pattern_signature(plan: OperationPlan | dict[str, Any]) -> str:
    data = plan.model_dump(mode="json") if hasattr(plan, "model_dump") else plan
    operations = data.get("operations", [])
    id_to_type = {operation.get("id"): operation.get("operation_type") for operation in operations}
    normalized: list[str] = []
    for operation in operations:
        op_type = operation.get("operation_type", "operation")
        refs: list[str] = []
        for key in ["target_id", "tool_id", "sketch_id", "profile_sketch_id", "path_sketch_id"]:
            ref = operation.get(key)
            if ref in id_to_type:
                refs.append(f"{key}:{id_to_type[ref]}")
        if "sketch_ids" in operation:
            refs.extend(f"sketch:{id_to_type.get(ref, 'unknown')}" for ref in operation.get("sketch_ids", []))
        normalized.append(op_type if not refs else f"{op_type}({','.join(sorted(refs))})")
    return "+".join(normalized)


def normalize_failure_signature(
    *,
    error_category: str,
    operation_type: str | None = None,
    message: str = "",
    capability_id: str | None = None,
    dimension_ratios: dict[str, float] | None = None,
) -> str:
    parts = [error_category]
    if operation_type:
        parts.append(operation_type)
    lowered = message.lower()
    for marker in ["oversized", "radius", "thin", "unknown", "future", "boolean", "shell", "hole"]:
        if marker in lowered:
            parts.append(marker)
    if capability_id:
        parts.append(f"capability:{capability_id}")
    for key, value in sorted((dimension_ratios or {}).items()):
        bucket = "low" if value < 0.25 else "mid" if value < 0.75 else "high"
        parts.append(f"{key}:{bucket}")
    return ":".join(parts)


def repair_strategy_signature(strategy: str, problem_signature: str) -> str:
    return f"{problem_signature}:{strategy.strip().lower().replace(' ', '_')}"


def status_counts(values: list[str]) -> dict[str, int]:
    counts = Counter(values)
    return {status.value: counts.get(status.value, 0) for status in EvidenceStatus}


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True)
