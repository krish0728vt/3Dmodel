from __future__ import annotations

from config import CONFIG
from learning.adaptive import normalize_failure_signature
from learning.models import EvidenceStatus
from learning.models import LessonRecord, RepairStrategyRecord, SuccessfulPatternRecord
from learning.store import LearningStore


def get_relevant_lessons(
    *,
    store: LearningStore,
    prompt: str | None = None,
    part_type: str | None = None,
    operation_types: list[str] | None = None,
    problem_signature: str | None = None,
    limit: int = 5,
) -> list[LessonRecord]:
    """Return lessons using deterministic metadata, trust status, and keyword overlap."""

    operation_types = operation_types or []
    prompt_words = _words(prompt or "")
    scored: list[tuple[float, LessonRecord]] = []
    for lesson in store.list_lessons(limit=200, include_deprecated=False):
        if lesson.status == EvidenceStatus.DEPRECATED:
            continue
        score = 0
        if part_type and part_type in lesson.applicable_part_types:
            score += 4
        score += 3 * len(set(operation_types) & set(lesson.applicable_operation_types))
        normalized_problem = normalize_failure_signature(error_category=problem_signature or "") if problem_signature else None
        if problem_signature and problem_signature == lesson.problem_signature:
            score += 5
        elif normalized_problem and normalized_problem == lesson.problem_signature:
            score += 4
        if lesson.status == EvidenceStatus.TRUSTED:
            score += 4
        elif lesson.status == EvidenceStatus.VALIDATED:
            score += 2
        elif lesson.status == EvidenceStatus.OBSERVED:
            score += 0.5
        lesson_words = _words(
            " ".join(
                [
                    lesson.title,
                    lesson.description,
                    lesson.problem_signature,
                    lesson.known_bad_pattern or "",
                    lesson.recommended_pattern or "",
                ]
            )
        )
        score += len(prompt_words & lesson_words)
        if score > 0:
            scored.append((score + lesson.confidence_score, lesson))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [lesson for _, lesson in scored[:limit]]


def get_relevant_patterns(
    *,
    store: LearningStore,
    operation_types: list[str],
    limit: int = 3,
) -> list[SuccessfulPatternRecord]:
    scored: list[tuple[float, SuccessfulPatternRecord]] = []
    for pattern in store.list_patterns(limit=200, include_deprecated=False):
        if pattern.status == EvidenceStatus.DEPRECATED:
            continue
        score = len(set(operation_types) & set(pattern.applicable_operation_types))
        if pattern.status == EvidenceStatus.TRUSTED:
            score += 4
        elif pattern.status == EvidenceStatus.VALIDATED:
            score += 2
        if score > 0:
            scored.append((score + pattern.confidence_score, pattern))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [pattern for _, pattern in scored[:limit]]


def get_relevant_repair_strategies(
    *,
    store: LearningStore,
    problem_signature: str | None = None,
    limit: int = 3,
) -> list[RepairStrategyRecord]:
    strategies = store.list_repair_strategies(
        problem_signature=problem_signature,
        limit=limit,
    )
    return [
        strategy
        for strategy in strategies
        if strategy.status != EvidenceStatus.DEPRECATED and strategy.successes > strategy.failures
    ][:limit]


def planning_context(
    *,
    store: LearningStore,
    prompt: str | None = None,
    part_type: str | None = None,
    operation_types: list[str] | None = None,
    problem_signature: str | None = None,
) -> dict[str, list[dict[str, object]]]:
    lessons = get_relevant_lessons(
        store=store,
        prompt=prompt,
        part_type=part_type,
        operation_types=operation_types or [],
        problem_signature=problem_signature,
        limit=CONFIG.planning_context_max_lessons,
    )
    patterns = get_relevant_patterns(
        store=store,
        operation_types=operation_types or [],
        limit=CONFIG.planning_context_max_patterns,
    )
    repair_strategies = get_relevant_repair_strategies(
        store=store,
        problem_signature=problem_signature,
        limit=CONFIG.planning_context_max_repair_strategies,
    )
    return {
        "lessons": [
            {
                "title": lesson.title,
                "status": lesson.status.value,
                "confidence": lesson.confidence_score,
                "description": lesson.description,
            }
            for lesson in lessons
        ],
        "patterns": [
            {
                "name": pattern.name,
                "status": pattern.status.value,
                "confidence": pattern.confidence_score,
                "operation_signature": pattern.operation_signature,
                "description": pattern.description,
            }
            for pattern in patterns
        ],
        "repair_strategies": [
            {
                "strategy": strategy.strategy,
                "strategy_signature": strategy.strategy_signature,
                "status": strategy.status.value,
                "confidence": strategy.confidence_score,
                "successes": strategy.successes,
                "failures": strategy.failures,
            }
            for strategy in repair_strategies
        ],
    }


def _words(text: str) -> set[str]:
    return {word.strip(".,:;()[]{}").lower() for word in text.split() if len(word) > 2}
