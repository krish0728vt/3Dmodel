from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from capabilities.registry import CapabilityRegistry
from api.dependencies import get_capability_registry
from learning.models import EvidenceStatus
from learning.store import LearningStore

from api.dependencies import get_learning_store


router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/stats")
def learning_stats(store: LearningStore = Depends(get_learning_store)) -> dict[str, Any]:
    return store.stats()


@router.get("/lessons")
def learning_lessons(store: LearningStore = Depends(get_learning_store)) -> list[dict[str, object]]:
    return [lesson.model_dump(mode="json") for lesson in store.list_lessons()]


@router.get("/lessons/{lesson_id}")
def learning_lesson(lesson_id: str, store: LearningStore = Depends(get_learning_store)) -> dict[str, object]:
    lesson = store.get_lesson(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found.")
    return lesson.model_dump(mode="json")


@router.post("/lessons/{lesson_id}/revalidate")
def revalidate_lesson(lesson_id: str, store: LearningStore = Depends(get_learning_store)) -> dict[str, object]:
    try:
        return store.record_lesson_evidence(lesson_id, success=True).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/lessons/{lesson_id}/deprecate")
def deprecate_lesson(lesson_id: str, store: LearningStore = Depends(get_learning_store)) -> dict[str, object]:
    try:
        return store.set_lesson_status(lesson_id, EvidenceStatus.DEPRECATED).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/patterns")
def learning_patterns(store: LearningStore = Depends(get_learning_store)) -> list[dict[str, object]]:
    return [pattern.model_dump(mode="json") for pattern in store.list_patterns()]


@router.get("/patterns/{pattern_id}")
def learning_pattern(pattern_id: str, store: LearningStore = Depends(get_learning_store)) -> dict[str, object]:
    pattern = store.get_pattern(pattern_id)
    if pattern is None:
        raise HTTPException(status_code=404, detail="Pattern not found.")
    return pattern.model_dump(mode="json")


@router.post("/patterns/{pattern_id}/revalidate")
def revalidate_pattern(pattern_id: str, store: LearningStore = Depends(get_learning_store)) -> dict[str, object]:
    try:
        return store.record_pattern_evidence(pattern_id, success=True).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/patterns/{pattern_id}/deprecate")
def deprecate_pattern(pattern_id: str, store: LearningStore = Depends(get_learning_store)) -> dict[str, object]:
    try:
        return store.set_pattern_status(pattern_id, EvidenceStatus.DEPRECATED).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/failures/analytics")
def failure_analytics(store: LearningStore = Depends(get_learning_store)) -> list[dict[str, object]]:
    return store.failure_analytics()


@router.get("/repair-strategies")
def repair_strategies(store: LearningStore = Depends(get_learning_store)) -> list[dict[str, object]]:
    return [strategy.model_dump(mode="json") for strategy in store.list_repair_strategies()]


@router.get("/capabilities/analytics")
def capability_analytics(registry: CapabilityRegistry = Depends(get_capability_registry)) -> list[dict[str, object]]:
    analytics: list[dict[str, object]] = []
    for capability in registry.list():
        metrics = capability.metrics
        success_rate = round((metrics.success_count / metrics.invocation_count) * 100, 1) if metrics.invocation_count else 0.0
        analytics.append(
            {
                "capability_id": capability.capability_id,
                "name": capability.name,
                "version": capability.version,
                "enabled": capability.enabled,
                "trust_level": capability.trust_level.value,
                "invocation_count": metrics.invocation_count,
                "success_count": metrics.success_count,
                "failure_count": metrics.failure_count,
                "success_rate": success_rate,
            }
        )
    return analytics
