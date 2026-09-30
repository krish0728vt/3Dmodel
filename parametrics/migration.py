from __future__ import annotations

from ai.schemas import OperationPlan


CURRENT_OPERATION_SCHEMA_VERSION = "1.2"
SUPPORTED_OPERATION_SCHEMA_VERSIONS = {"1.0", "1.1", CURRENT_OPERATION_SCHEMA_VERSION}


def normalize_operation_schema_version(plan: OperationPlan) -> OperationPlan:
    if plan.schema_version not in SUPPORTED_OPERATION_SCHEMA_VERSIONS:
        raise ValueError(f"Unsupported OperationPlan schema_version: {plan.schema_version}")
    plan.schema_version = CURRENT_OPERATION_SCHEMA_VERSION
    return plan
