from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from ai.schemas import OperationPlan
from cad.generator import generate_step
from cad.operation_executor import execute_operation_plan
from cad.operation_validator import validate_operation_plan
from config import CONFIG
from learning.classifier import classify_failure
from learning.adaptive import normalize_failure_signature, repair_strategy_signature
from learning.retrieval import get_relevant_lessons, get_relevant_patterns, get_relevant_repair_strategies
from learning.store import LearningStore


class PlanRepairProvider(Protocol):
    def repair_plan(
        self,
        *,
        original_prompt: str,
        original_plan: OperationPlan,
        failure_category: str,
        failure_message: str,
        lessons: list[str],
        patterns: list[str],
        repair_strategies: list[str],
        available_operations: list[str],
    ) -> OperationPlan:
        """Return a corrected structured plan."""


AVAILABLE_OPERATIONS = [
    "create_box",
    "create_cylinder",
    "create_sketch_rectangle",
    "create_sketch_circle",
    "extrude",
    "revolve",
    "cut_hole",
    "boolean_union",
    "boolean_cut",
    "fillet",
    "chamfer",
    "linear_pattern",
    "circular_pattern",
    "mirror",
]


def generate_with_repair(
    *,
    prompt: str,
    plan: OperationPlan,
    output_path: str | Path,
    repair_provider: PlanRepairProvider,
    store: LearningStore | None = None,
    max_attempts: int | None = None,
) -> OperationPlan:
    """Execute/export a plan, optionally attempting bounded structured repairs."""

    store = store or LearningStore()
    max_attempts = CONFIG.max_repair_attempts if max_attempts is None else max_attempts
    current_plan = plan
    failure_id: str | None = None

    for attempt in range(0, max_attempts + 1):
        try:
            validate_operation_plan(current_plan)
            execute_operation_plan(current_plan)
            generate_step(current_plan, output_path)
            if attempt > 0 and failure_id is not None:
                store.record_repair_attempt(
                    failure_id=failure_id,
                    attempt_number=attempt,
                    repaired_plan_json=current_plan.model_dump_json(),
                    strategy="bounded_structured_repair",
                    result="success",
                    strategy_signature=repair_strategy_signature("bounded_structured_repair", _failure_signature(store, failure_id)),
                )
                store.insert_lesson(
                    title="Structured repair succeeded",
                    description="A previously failing operation plan was corrected by a bounded structured repair.",
                    problem_signature=failure_id,
                    applicable_operation_types=_operation_types(current_plan),
                    recommended_pattern=current_plan.model_dump_json(),
                    success_count=1,
                    confidence=0.25,
                )
            maybe_record_successful_pattern(store, current_plan)
            return current_plan
        except Exception as exc:
            category = classify_failure(exc)
            if failure_id is None:
                failure_id = store.record_failure(
                    error_category=category,
                    error_message=str(exc),
                    prompt=prompt,
                    operation_plan_json=current_plan.model_dump_json(),
                    normalized_signature=normalize_failure_signature(
                        error_category=category.value,
                        operation_type=_operation_types(current_plan)[-1] if _operation_types(current_plan) else None,
                        message=str(exc),
                    ),
                )
            normalized_problem = _failure_signature(store, failure_id) if failure_id else category.value
            if attempt >= max_attempts:
                if failure_id is not None:
                    store.record_repair_attempt(
                        failure_id=failure_id,
                        attempt_number=attempt + 1,
                        strategy="bounded_structured_repair",
                        result="exhausted",
                        error_message=str(exc),
                        strategy_signature=repair_strategy_signature("bounded_structured_repair", normalized_problem),
                    )
                raise

            lessons = get_relevant_lessons(
                store=store,
                prompt=prompt,
                operation_types=_operation_types(current_plan),
                problem_signature=category.value,
                limit=5,
            )
            patterns = get_relevant_patterns(
                store=store,
                operation_types=_operation_types(current_plan),
                limit=3,
            )
            repair_strategies = get_relevant_repair_strategies(
                store=store,
                problem_signature=normalized_problem,
                limit=CONFIG.planning_context_max_repair_strategies,
            )
            try:
                repaired_plan = repair_provider.repair_plan(
                    original_prompt=prompt,
                    original_plan=current_plan,
                    failure_category=category.value,
                    failure_message=str(exc),
                    lessons=[lesson.description for lesson in lessons],
                    patterns=[pattern.description for pattern in patterns],
                    repair_strategies=[
                        f"{strategy.strategy} ({strategy.successes} successes, confidence {strategy.confidence_score})"
                        for strategy in repair_strategies
                    ],
                    available_operations=AVAILABLE_OPERATIONS,
                )
                validate_operation_plan(repaired_plan)
                store.record_repair_attempt(
                    failure_id=failure_id,
                    attempt_number=attempt + 1,
                    repaired_plan_json=repaired_plan.model_dump_json(),
                    strategy="bounded_structured_repair",
                    result="candidate",
                    strategy_signature=repair_strategy_signature("bounded_structured_repair", normalized_problem),
                )
                current_plan = repaired_plan
            except (ValidationError, Exception) as repair_exc:
                store.record_repair_attempt(
                    failure_id=failure_id,
                    attempt_number=attempt + 1,
                    repaired_plan_json=None,
                    strategy="bounded_structured_repair",
                    result="invalid",
                    error_message=str(repair_exc),
                    strategy_signature=repair_strategy_signature("bounded_structured_repair", normalized_problem),
                )
                if attempt + 1 >= max_attempts:
                    raise repair_exc

    return current_plan


def maybe_record_successful_pattern(store: LearningStore, plan: OperationPlan) -> str | None:
    """Record reusable non-trivial operation plans after successful generation."""

    operation_types = _operation_types(plan)
    if len(operation_types) < 2:
        return None
    reusable_markers = {
        "boolean_union",
        "cut_hole",
        "mirror",
        "linear_pattern",
        "circular_pattern",
    }
    if not (set(operation_types) & reusable_markers):
        return None
    return store.record_successful_pattern(
        name=plan.project_name,
        description=f"Reusable operation sequence for {plan.project_name}.",
        applicable_operation_types=operation_types,
        input_signature=",".join(operation_types),
        plan_fragment_json=plan.model_dump_json(),
        validation_notes="Recorded after schema validation, operation validation, execution, and STEP export.",
    )


def create_regression_candidate(
    *,
    store: LearningStore,
    failure_id: str,
    output_dir: str | Path = "tests/regressions",
) -> Path:
    failure = store.get_failure(failure_id)
    if failure is None:
        raise ValueError(f"Unknown failure_id: {failure_id}")
    path = Path(output_dir) / f"test_failure_{failure_id}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f'''"""Candidate regression generated by SHAH LEARNING CORE.

Failure ID: {failure_id}
Category: {failure.error_category.value}
"""

import pytest


def test_failure_{failure_id}_candidate():
    # Original error:
    # {failure.error_message.replace(chr(10), " ")}
    pytest.skip("Review this generated candidate before enabling it in the normal suite.")
'''
    path.write_text(content, encoding="utf-8")
    return path


def _operation_types(plan: OperationPlan) -> list[str]:
    return [operation.operation_type for operation in plan.operations]


def _failure_signature(store: LearningStore, failure_id: str) -> str:
    failure = store.get_failure(failure_id)
    if failure is None:
        return "unknown_failure"
    if failure.normalized_signature:
        return failure.normalized_signature
    return normalize_failure_signature(
        error_category=failure.error_category.value,
        message=failure.error_message,
    )
