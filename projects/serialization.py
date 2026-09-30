from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from ai.schemas import OperationPlan, SupportedPartSpec
from parametrics.migration import normalize_operation_schema_version


PART_ADAPTER = TypeAdapter(SupportedPartSpec)


def model_type_for(model: SupportedPartSpec | OperationPlan) -> str:
    return "operation_plan" if isinstance(model, OperationPlan) else "template"


def model_to_json(model: SupportedPartSpec | OperationPlan) -> str:
    return model.model_dump_json()


def model_from_json(model_type: str, raw_json: str) -> SupportedPartSpec | OperationPlan:
    if model_type == "operation_plan":
        return normalize_operation_schema_version(OperationPlan.model_validate_json(raw_json))
    return PART_ADAPTER.validate_json(raw_json)


def model_to_dict(model: SupportedPartSpec | OperationPlan) -> dict[str, Any]:
    return model.model_dump(mode="json")
