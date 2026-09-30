from __future__ import annotations

import pytest

from ai.schemas import (
    BooleanUnionOperation,
    CreateBoxOperation,
    CreateCylinderOperation,
    OperationPlan,
)
from cad.operation_validator import OperationValidationError, validate_operation_plan
from learning.classifier import classify_failure
from learning.models import FailureCategory
from learning.repair import (
    create_regression_candidate,
    generate_with_repair,
    maybe_record_successful_pattern,
)
from learning.retrieval import get_relevant_lessons
from learning.store import LearningStore


def valid_plan() -> OperationPlan:
    return OperationPlan(
        project_name="base_with_boss",
        operations=[
            CreateBoxOperation(id="base", width_mm=20, depth_mm=20, height_mm=5),
            CreateCylinderOperation(id="boss", diameter_mm=8, height_mm=10, center=(0, 0, 7.5)),
            BooleanUnionOperation(id="combined", target_id="base", tool_id="boss"),
        ],
        final_object_id="combined",
    )


def invalid_plan() -> OperationPlan:
    return OperationPlan(
        project_name="bad_reference",
        operations=[BooleanUnionOperation(id="combined", target_id="base", tool_id="boss")],
    )


def test_learning_store_insert_and_read(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.db")

    failure_id = store.record_failure(
        error_category=FailureCategory.INVALID_REFERENCE,
        error_message="unknown reference",
        prompt="make a bad part",
    )
    lesson_id = store.insert_lesson(
        title="Avoid future references",
        description="Create solids before referencing them.",
        problem_signature="invalid_reference",
        applicable_operation_types=["boolean_union"],
    )
    pattern_id = store.record_successful_pattern(
        name="base boss",
        description="Base plus centered boss.",
        applicable_operation_types=["create_box", "create_cylinder", "boolean_union"],
        input_signature="base,boss",
        plan_fragment_json=valid_plan().model_dump_json(),
    )
    repair_id = store.record_repair_attempt(
        failure_id=failure_id,
        attempt_number=1,
        strategy="mock",
        result="success",
        repaired_plan_json=valid_plan().model_dump_json(),
    )

    assert store.get_failure(failure_id) is not None
    assert store.get_lesson(lesson_id) is not None
    assert store.list_patterns()[0].pattern_id == pattern_id
    assert store.list_repair_attempts(failure_id)[0].repair_id == repair_id
    assert store.stats()["resolved"] == 1


def test_failure_classification_known_and_unknown() -> None:
    with pytest.raises(OperationValidationError) as exc_info:
        validate_operation_plan(invalid_plan())

    assert classify_failure(exc_info.value) == FailureCategory.FORWARD_REFERENCE
    assert classify_failure(RuntimeError("boolean operation failed")) == FailureCategory.BOOLEAN_FAILURE
    assert classify_failure(RuntimeError("STEP export failed")) == FailureCategory.EXPORT_FAILURE
    assert classify_failure(Exception("surprising")) == FailureCategory.UNKNOWN_FAILURE


def test_relevant_lesson_matching_and_limit(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    store.insert_lesson(
        title="Boolean operands must exist",
        description="Create base and boss before boolean union.",
        problem_signature="invalid_reference",
        applicable_operation_types=["boolean_union"],
    )
    store.insert_lesson(
        title="Unrelated fillet lesson",
        description="Avoid oversized fillets.",
        problem_signature="fillet_failure",
        applicable_operation_types=["fillet"],
    )

    lessons = get_relevant_lessons(
        store=store,
        prompt="base boss union",
        operation_types=["boolean_union"],
        limit=1,
    )

    assert len(lessons) == 1
    assert lessons[0].problem_signature == "invalid_reference"


class StaticRepairProvider:
    def __init__(self, plans: list[OperationPlan]) -> None:
        self.plans = plans
        self.calls = 0

    def repair_plan(self, **_: object) -> OperationPlan:
        plan = self.plans[self.calls]
        self.calls += 1
        return plan


def test_repair_loop_first_attempt_succeeds(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    provider = StaticRepairProvider([])

    result = generate_with_repair(
        prompt="valid plan",
        plan=valid_plan(),
        output_path=tmp_path / "valid.step",
        repair_provider=provider,
        store=store,
    )

    assert result.project_name == "base_with_boss"
    assert provider.calls == 0


def test_repair_loop_one_repair_succeeds(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    provider = StaticRepairProvider([valid_plan()])

    result = generate_with_repair(
        prompt="repair this",
        plan=invalid_plan(),
        output_path=tmp_path / "repaired.step",
        repair_provider=provider,
        store=store,
        max_attempts=2,
    )

    assert result.project_name == "base_with_boss"
    assert store.stats()["resolved"] == 1
    assert store.stats()["lessons"] == 1


def test_repair_loop_exhaustion_and_invalid_repair(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    provider = StaticRepairProvider([invalid_plan(), invalid_plan()])

    with pytest.raises(OperationValidationError):
        generate_with_repair(
            prompt="cannot repair",
            plan=invalid_plan(),
            output_path=tmp_path / "bad.step",
            repair_provider=provider,
            store=store,
            max_attempts=2,
        )

    assert store.stats()["repairs"] >= 1


def test_successful_pattern_recording_heuristic(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.db")

    pattern_id = maybe_record_successful_pattern(store, valid_plan())
    trivial = maybe_record_successful_pattern(
        store,
        OperationPlan(
            project_name="plain_box",
            operations=[CreateBoxOperation(id="box", width_mm=10, depth_mm=10, height_mm=10)],
        ),
    )

    assert pattern_id is not None
    assert trivial is None


def test_regression_candidate_generation(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    failure_id = store.record_failure(
        error_category=FailureCategory.INVALID_GEOMETRY,
        error_message="bad geometry",
    )

    path = create_regression_candidate(
        store=store,
        failure_id=failure_id,
        output_dir=tmp_path / "regressions",
    )

    assert path.exists()
    assert failure_id in path.read_text(encoding="utf-8")
