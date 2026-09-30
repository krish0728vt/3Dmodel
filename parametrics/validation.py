from __future__ import annotations

from ai.schemas import OperationPlan, SupportedPartSpec
from parametrics.resolver import ParametricResolutionError, resolve_design_intent


def validate_design_intent(model: SupportedPartSpec | OperationPlan) -> None:
    """Validate that a model's optional design intent can resolve deterministically."""

    try:
        resolve_design_intent(model)
    except ParametricResolutionError:
        raise
