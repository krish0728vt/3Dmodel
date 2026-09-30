from __future__ import annotations

import json
from pathlib import Path

from evaluation.models import EvaluationReport


REPORT_DIR = Path("outputs") / "evaluation"
LATEST_JSON = REPORT_DIR / "latest.json"
LATEST_MD = REPORT_DIR / "latest.md"


def write_reports(report: EvaluationReport, *, report_dir: Path = REPORT_DIR) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "latest.json"
    md_path = report_dir / "latest.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(markdown_report(report), encoding="utf-8")
    return json_path, md_path


def load_latest(*, path: Path = LATEST_JSON) -> EvaluationReport | None:
    if not path.exists():
        return None
    return EvaluationReport.model_validate(json.loads(path.read_text(encoding="utf-8")))


def markdown_report(report: EvaluationReport) -> str:
    metrics = report.metrics
    lines = [
        "# SHAH INDUSTRIES Evaluation Report",
        "",
        f"Suite: `{report.suite}`",
        f"Generated: `{report.generated_at}`",
        f"Cases: {metrics.total_cases}",
        f"Passed: {metrics.pass_count}",
        f"Failed: {metrics.fail_count}",
        f"Unsupported: {metrics.unsupported_count}",
        f"Skipped: {metrics.skipped_count}",
        "",
        "## Stage Rates",
        "",
        f"- Parser: {metrics.parse_success_rate}%",
        f"- Schema: {metrics.schema_success_rate}%",
        f"- CAD generation: {metrics.cad_generation_success_rate}%",
        f"- STEP export: {metrics.step_export_success_rate}%",
        f"- STL export: {metrics.stl_export_success_rate}%",
        f"- Repair success: {metrics.repair_success_rate}%",
        "",
        "## Categories",
        "",
    ]
    for category, data in metrics.category.items():
        lines.append(f"- {category}: {data['pass']}/{data['total']} pass ({data['success_rate']}%)")
    lines.extend(["", "## Difficulty", ""])
    for difficulty, data in metrics.difficulty.items():
        lines.append(f"- {difficulty}: {data['pass']}/{data['total']} pass ({data['success_rate']}%)")
    lines.extend(["", "## Failure Distribution", ""])
    if metrics.failure_distribution:
        for category, count in sorted(metrics.failure_distribution.items()):
            lines.append(f"- {category}: {count}")
    else:
        lines.append("- none")
    lines.extend(["", "## Regressions", ""])
    if report.regressions:
        for regression in report.regressions:
            lines.append(f"- {regression.case_id}: {regression.regression_type} - {regression.message}")
    else:
        lines.append("- none")
    lines.extend(["", "## Failed Cases", ""])
    failed = [result for result in report.results if result.overall_status.value == "fail"]
    if failed:
        for result in failed:
            lines.append(f"- {result.case_id}: {result.failure_category} - {result.failure_message}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"
