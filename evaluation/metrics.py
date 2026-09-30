from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from evaluation.models import BenchmarkMode, BenchmarkResult, BenchmarkStatus, EvaluationMetrics


def calculate_metrics(results: list[BenchmarkResult]) -> EvaluationMetrics:
    total = len(results)
    pass_count = sum(1 for result in results if result.overall_status == BenchmarkStatus.PASS)
    fail_count = sum(1 for result in results if result.overall_status == BenchmarkStatus.FAIL)
    unsupported_count = sum(1 for result in results if result.overall_status == BenchmarkStatus.UNSUPPORTED)
    skipped_count = sum(1 for result in results if result.overall_status == BenchmarkStatus.SKIPPED)
    duration = sum(result.duration_ms for result in results)

    return EvaluationMetrics(
        total_cases=total,
        pass_count=pass_count,
        fail_count=fail_count,
        unsupported_count=unsupported_count,
        skipped_count=skipped_count,
        parse_success_rate=_rate(results, "parse_success"),
        schema_success_rate=_rate(results, "schema_validation_success"),
        cad_generation_success_rate=_rate(results, "cad_generation_success"),
        step_export_success_rate=_rate([r for r in results if "step" in r.metrics.get("expected_exports", [])], "step_export_success"),
        stl_export_success_rate=_rate([r for r in results if "stl" in r.metrics.get("expected_exports", [])], "stl_export_success"),
        repair_success_rate=_repair_rate(results),
        parametric_preservation_rate=_mode_rate(results, BenchmarkMode.PARAMETRIC, "expected_structure_match"),
        assembly_success_rate=_mode_status_rate(results, BenchmarkMode.ASSEMBLY),
        capability_success_rate=_mode_status_rate(results, BenchmarkMode.CAPABILITY),
        category=_bucket(results, "category"),
        difficulty=_bucket(results, "difficulty"),
        failure_distribution=dict(Counter(result.failure_category.value for result in results if result.failure_category)),
        total_duration_ms=duration,
        average_duration_ms=round(duration / total, 2) if total else 0,
        slowest_cases=[
            {"case_id": result.case_id, "duration_ms": result.duration_ms, "status": result.overall_status.value}
            for result in sorted(results, key=lambda item: item.duration_ms, reverse=True)[:5]
        ],
    )


def _rate(results: list[BenchmarkResult], field: str) -> float:
    if not results:
        return 0.0
    return round(100 * sum(1 for result in results if bool(getattr(result, field))) / len(results), 2)


def _mode_rate(results: list[BenchmarkResult], mode: BenchmarkMode, field: str) -> float:
    matching = [result for result in results if result.mode == mode]
    return _rate(matching, field)


def _mode_status_rate(results: list[BenchmarkResult], mode: BenchmarkMode) -> float:
    matching = [
        result
        for result in results
        if result.mode == mode and result.overall_status not in {BenchmarkStatus.UNSUPPORTED, BenchmarkStatus.SKIPPED}
    ]
    if not matching:
        return 0.0
    return round(100 * sum(1 for result in matching if result.overall_status == BenchmarkStatus.PASS) / len(matching), 2)


def _repair_rate(results: list[BenchmarkResult]) -> float:
    attempted = [result for result in results if result.repair_attempted]
    if not attempted:
        return 0.0
    return round(100 * sum(1 for result in attempted if result.repair_success) / len(attempted), 2)


def _bucket(results: list[BenchmarkResult], field: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[BenchmarkResult]] = defaultdict(list)
    for result in results:
        value = getattr(result, field)
        buckets[value.value].append(result)
    return {
        key: {
            "total": len(items),
            "pass": sum(1 for item in items if item.overall_status == BenchmarkStatus.PASS),
            "fail": sum(1 for item in items if item.overall_status == BenchmarkStatus.FAIL),
            "unsupported": sum(1 for item in items if item.overall_status == BenchmarkStatus.UNSUPPORTED),
            "success_rate": round(100 * sum(1 for item in items if item.overall_status == BenchmarkStatus.PASS) / len(items), 2),
        }
        for key, items in sorted(buckets.items())
    }
