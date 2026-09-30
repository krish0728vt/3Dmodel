from __future__ import annotations

import json
from pathlib import Path

from evaluation.models import BenchmarkStatus, EvaluationReport, RegressionRecord


BASELINE_PATH = Path("benchmarks") / "baselines" / "current.json"


def load_baseline(path: Path = BASELINE_PATH) -> EvaluationReport | None:
    if not path.exists():
        return None
    return EvaluationReport.model_validate(json.loads(path.read_text(encoding="utf-8")))


def save_baseline(report: EvaluationReport, path: Path = BASELINE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def compare_to_baseline(current: EvaluationReport, baseline: EvaluationReport | None) -> list[RegressionRecord]:
    if baseline is None:
        return []
    previous = {result.case_id: result for result in baseline.results}
    regressions: list[RegressionRecord] = []
    for result in current.results:
        prior = previous.get(result.case_id)
        if prior is None:
            continue
        if prior.overall_status == BenchmarkStatus.PASS and result.overall_status == BenchmarkStatus.FAIL:
            regressions.append(
                RegressionRecord(
                    case_id=result.case_id,
                    previous_status=prior.overall_status,
                    current_status=result.overall_status,
                    regression_type="pass_to_fail",
                    message=result.failure_message or "Previously passing case now fails.",
                )
            )
        if prior.overall_status == BenchmarkStatus.PASS and result.overall_status == BenchmarkStatus.UNSUPPORTED:
            regressions.append(
                RegressionRecord(
                    case_id=result.case_id,
                    previous_status=prior.overall_status,
                    current_status=result.overall_status,
                    regression_type="pass_to_unsupported",
                    message="Previously supported case is now unsupported.",
                )
            )
        if prior.step_export_success and not result.step_export_success:
            regressions.append(
                RegressionRecord(
                    case_id=result.case_id,
                    previous_status=prior.overall_status,
                    current_status=result.overall_status,
                    regression_type="step_export_regression",
                    message="STEP export no longer succeeds.",
                )
            )
        if prior.mode.value == "parametric" and prior.expected_structure_match and not result.expected_structure_match:
            regressions.append(
                RegressionRecord(
                    case_id=result.case_id,
                    previous_status=prior.overall_status,
                    current_status=result.overall_status,
                    regression_type="parametric_preservation_regression",
                    message="Parametric structural expectation no longer holds.",
                )
            )
    return regressions
