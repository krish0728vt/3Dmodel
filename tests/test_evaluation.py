from __future__ import annotations

import json

from evaluation.baselines import compare_to_baseline
from evaluation.categories import BenchmarkCategory
from evaluation.fixtures import load_cases
from evaluation.metrics import calculate_metrics
from evaluation.models import BenchmarkStatus, EvaluationReport, RegressionRecord
from evaluation.reporting import markdown_report, write_reports
from evaluation.runner import evaluate_case


def test_benchmark_loading_and_filters() -> None:
    all_cases = load_cases()
    assert len(all_cases) >= 20
    assert load_cases(category=BenchmarkCategory.PARAMETRICS)
    assert all(case.difficulty.value == "complex" for case in load_cases(difficulty="complex"))
    assert load_cases(case_id="basic_cube_050")[0].case_id == "basic_cube_050"
    assert len(load_cases(smoke=True)) >= 20


def test_basic_case_stage_results_and_metrics(tmp_path) -> None:
    case = load_cases(case_id="basic_cube_050")[0]
    result = evaluate_case(case, tmp_path / case.case_id)
    assert result.overall_status == BenchmarkStatus.PASS
    assert result.parse_success
    assert result.schema_validation_success
    assert result.cad_generation_success
    assert result.step_export_success
    assert result.stl_export_success
    assert result.expected_structure_match
    assert result.metrics["geometry"]["solid_count"] == 1

    metrics = calculate_metrics([result])
    assert metrics.total_cases == 1
    assert metrics.pass_count == 1
    assert metrics.cad_generation_success_rate == 100


def test_unsupported_and_ambiguity_classification(tmp_path) -> None:
    unsupported = evaluate_case(load_cases(case_id="unsupported_jet_engine")[0], tmp_path / "unsupported")
    ambiguous = evaluate_case(load_cases(case_id="ambiguous_make_cylinder_taller")[0], tmp_path / "ambiguous")
    assert unsupported.overall_status == BenchmarkStatus.UNSUPPORTED
    assert unsupported.failure_category.value == "expected_unsupported"
    assert ambiguous.overall_status == BenchmarkStatus.SKIPPED
    assert ambiguous.failure_category.value == "expected_ambiguity"


def test_report_generation_and_baseline_regression(tmp_path) -> None:
    passing = evaluate_case(load_cases(case_id="basic_cube_050")[0], tmp_path / "passing")
    report = EvaluationReport(
        suite="unit",
        generated_at="2026-09-30T00:00:00+00:00",
        case_count=1,
        metrics=calculate_metrics([passing]),
        results=[passing],
    )
    json_path, md_path = write_reports(report, report_dir=tmp_path / "reports")
    assert json.loads(json_path.read_text(encoding="utf-8"))["case_count"] == 1
    assert "SHAH INDUSTRIES Evaluation Report" in md_path.read_text(encoding="utf-8")
    assert "CAD generation" in markdown_report(report)

    failing = passing.model_copy(update={"overall_status": BenchmarkStatus.FAIL, "failure_message": "forced"})
    current = report.model_copy(update={"results": [failing], "metrics": calculate_metrics([failing])})
    regressions = compare_to_baseline(current, report)
    assert regressions
    assert regressions[0].regression_type == "pass_to_fail"
