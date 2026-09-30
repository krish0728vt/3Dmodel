from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from ai.schemas import BooleanUnionOperation, CreateBoxOperation, CreateCylinderOperation, OperationPlan
from api.dependencies import get_capability_registry, get_learning_store
from api.server import create_app
from capabilities.registry import CapabilityRegistry
from learning.adaptive import calculate_confidence, normalize_failure_signature, normalize_pattern_signature, repair_strategy_signature
from learning.models import EvidenceStatus, FailureCategory
from learning.retrieval import get_relevant_lessons, get_relevant_repair_strategies, planning_context
from learning.store import LearningStore


def _boss_plan(box_id: str = "base", boss_id: str = "boss") -> OperationPlan:
    return OperationPlan(
        project_name="boss_plan",
        operations=[
            CreateBoxOperation(id=box_id, width_mm=20, depth_mm=20, height_mm=5),
            CreateCylinderOperation(id=boss_id, diameter_mm=8, height_mm=10, center=(0, 0, 7.5)),
            BooleanUnionOperation(id="union", target_id=box_id, tool_id=boss_id),
        ],
        final_object_id="union",
    )


def test_lesson_lifecycle_promotion_and_contradiction(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    lesson_id = store.insert_lesson(
        title="Boolean overlap",
        description="Boss unions need overlap.",
        problem_signature="boolean_failure:boolean",
        applicable_operation_types=["boolean_union"],
    )
    lesson = store.get_lesson(lesson_id)
    assert lesson.status == EvidenceStatus.OBSERVED

    for _ in range(2):
        lesson = store.record_lesson_evidence(lesson_id, success=True)
    assert lesson.status == EvidenceStatus.VALIDATED

    for _ in range(5):
        lesson = store.record_lesson_evidence(lesson_id, success=True)
    assert lesson.status == EvidenceStatus.TRUSTED

    before = lesson.confidence_score
    lesson = store.record_lesson_evidence(lesson_id, success=False, contradiction=True)
    assert lesson.confidence_score < before

    lesson = store.set_lesson_status(lesson_id, EvidenceStatus.DEPRECATED)
    assert lesson.status == EvidenceStatus.DEPRECATED
    assert get_relevant_lessons(store=store, operation_types=["boolean_union"]) == []


def test_confidence_formula_is_deterministic() -> None:
    low = calculate_confidence(success_count=1, failure_count=0, contradiction_count=0)
    high = calculate_confidence(success_count=8, failure_count=0, contradiction_count=0)
    contradicted = calculate_confidence(success_count=8, failure_count=0, contradiction_count=2)

    assert low < high
    assert contradicted < high
    assert calculate_confidence(success_count=8, failure_count=0, contradiction_count=0) == high


def test_pattern_signature_ignores_ids_but_preserves_structure() -> None:
    first = normalize_pattern_signature(_boss_plan("base", "boss"))
    second = normalize_pattern_signature(_boss_plan("plate", "post"))
    different = normalize_pattern_signature(
        OperationPlan(project_name="box", operations=[CreateBoxOperation(id="box", width_mm=1, depth_mm=1, height_mm=1)])
    )

    assert first == second
    assert first != different


def test_failure_signature_groups_semantic_features() -> None:
    signature = normalize_failure_signature(
        error_category=FailureCategory.FILLET_FAILURE.value,
        operation_type="fillet",
        message="oversized radius on thin plate",
        dimension_ratios={"fillet_radius_over_thickness": 0.9},
    )

    assert "fillet_failure" in signature
    assert "oversized" in signature
    assert "fillet_radius_over_thickness:high" in signature


def test_pattern_lifecycle_and_migration(tmp_path) -> None:
    db_path = tmp_path / "learning.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE lessons (
                lesson_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                problem_signature TEXT NOT NULL,
                applicable_part_types TEXT NOT NULL,
                applicable_operation_types TEXT NOT NULL,
                known_bad_pattern TEXT,
                recommended_pattern TEXT,
                evidence_count INTEGER NOT NULL,
                success_count INTEGER NOT NULL,
                failure_count INTEGER NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL,
                last_verified_at TEXT
            );
            INSERT INTO lessons VALUES ('lesson_old', 'Old', 'Old lesson', 'x', '[]', '["fillet"]', NULL, NULL, 1, 1, 0, 0.2, '2026-01-01T00:00:00+00:00', NULL);
            """
        )

    store = LearningStore(db_path)
    lesson = store.get_lesson("lesson_old")
    assert lesson is not None
    assert lesson.status == EvidenceStatus.OBSERVED

    pattern_id = store.record_successful_pattern(
        name="boss pattern",
        description="base plus boss",
        applicable_operation_types=["create_box", "create_cylinder", "boolean_union"],
        input_signature="legacy",
        plan_fragment_json=_boss_plan().model_dump_json(),
    )
    pattern = store.record_pattern_evidence(pattern_id, success=True)
    assert pattern.usage_count == 2
    assert pattern.operation_signature is not None


def test_learning_api_and_capability_analytics(tmp_path) -> None:
    learning = LearningStore(tmp_path / "learning.db")
    registry = CapabilityRegistry(tmp_path / "caps.json")
    lesson_id = learning.insert_lesson(
        title="Shell caution",
        description="Keep shell thickness proportional.",
        problem_signature="shell_failure",
        applicable_operation_types=["shell"],
    )
    pattern_id = learning.record_successful_pattern(
        name="boss",
        description="boss pattern",
        applicable_operation_types=["boolean_union"],
        input_signature="boss",
        plan_fragment_json=_boss_plan().model_dump_json(),
    )
    capability = registry.discover_local_adapter("spur_gear_generator")
    registry.record_invocation(capability.capability_id, success=True)

    app = create_app()
    app.dependency_overrides[get_learning_store] = lambda: learning
    app.dependency_overrides[get_capability_registry] = lambda: registry
    client = TestClient(app)

    assert client.get("/api/learning/lessons").status_code == 200
    assert client.get(f"/api/learning/lessons/{lesson_id}").status_code == 200
    assert client.post(f"/api/learning/lessons/{lesson_id}/revalidate").status_code == 200
    assert client.post(f"/api/learning/patterns/{pattern_id}/deprecate").json()["status"] == "DEPRECATED"
    assert client.get("/api/learning/failures/analytics").status_code == 200
    assert client.get("/api/learning/repair-strategies").status_code == 200
    analytics = client.get("/api/learning/capabilities/analytics").json()
    assert any(item["capability_id"] == capability.capability_id and item["success_count"] == 1 for item in analytics)


def test_evidence_event_ids_are_idempotent(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    lesson_id = store.insert_lesson(
        title="Shell caution",
        description="Shell thickness must stay proportional.",
        problem_signature="shell_failure",
        applicable_operation_types=["shell"],
    )
    pattern_id = store.record_successful_pattern(
        name="boss",
        description="boss pattern",
        applicable_operation_types=["boolean_union"],
        input_signature="boss",
        plan_fragment_json=_boss_plan().model_dump_json(),
    )

    first_lesson = store.record_lesson_evidence(lesson_id, success=True, event_id="regression:lesson:1")
    second_lesson = store.record_lesson_evidence(lesson_id, success=True, event_id="regression:lesson:1")
    first_pattern = store.record_pattern_evidence(pattern_id, success=True, event_id="regression:pattern:1")
    second_pattern = store.record_pattern_evidence(pattern_id, success=True, event_id="regression:pattern:1")

    assert first_lesson.success_count == second_lesson.success_count
    assert first_pattern.success_count == second_pattern.success_count


def test_version_change_marks_records_needing_revalidation(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    lesson_id = store.insert_lesson(
        title="Capability lesson",
        description="A versioned capability lesson.",
        problem_signature="capability:gear",
        applicable_operation_types=["capability_invocation"],
        source_capability_versions={"gear": "1.0"},
        source_engine_version="1.0",
    )
    pattern_id = store.record_successful_pattern(
        name="gear pattern",
        description="gear pattern",
        applicable_operation_types=["capability_invocation"],
        input_signature="gear",
        plan_fragment_json=_boss_plan().model_dump_json(),
        source_capabilities={"gear": "1.0"},
    )

    result = store.mark_records_needing_revalidation(engine_version="2.0", capability_versions={"gear": "2.0"})

    assert result == {"lessons": 1, "patterns": 1}
    assert store.get_lesson(lesson_id).status == EvidenceStatus.NEEDS_REVALIDATION  # type: ignore[union-attr]
    assert store.get_pattern(pattern_id).status == EvidenceStatus.NEEDS_REVALIDATION  # type: ignore[union-attr]


def test_repair_strategy_memory_and_planning_context(tmp_path) -> None:
    store = LearningStore(tmp_path / "learning.db")
    signature = normalize_failure_signature(
        error_category=FailureCategory.BOOLEAN_FAILURE.value,
        operation_type="boolean_union",
        message="boolean failed",
    )
    failure_id = store.record_failure(
        error_category=FailureCategory.BOOLEAN_FAILURE,
        error_message="boolean failed",
        normalized_signature=signature,
    )
    strategy_signature = repair_strategy_signature("increase overlap", signature)

    store.record_repair_attempt(
        failure_id=failure_id,
        attempt_number=1,
        strategy="increase overlap",
        result="invalid",
        strategy_signature=strategy_signature,
    )
    assert get_relevant_repair_strategies(store=store, problem_signature=signature) == []

    store.record_repair_attempt(
        failure_id=failure_id,
        attempt_number=2,
        strategy="increase overlap",
        result="success",
        strategy_signature=strategy_signature,
    )
    store.record_repair_attempt(
        failure_id=failure_id,
        attempt_number=3,
        strategy="increase overlap",
        result="success",
        strategy_signature=strategy_signature,
    )

    strategies = get_relevant_repair_strategies(store=store, problem_signature=signature)
    context = planning_context(store=store, operation_types=["boolean_union"], problem_signature=signature)

    assert strategies[0].successes == 2
    assert strategies[0].failures == 1
    assert context["repair_strategies"][0]["strategy_signature"] == strategy_signature
