from __future__ import annotations

import argparse
import os
import shutil
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from pydantic import TypeAdapter

from ai.schemas import OperationPlan, SupportedDesignSpec
from assemblies.manager import assembly_engineering, assembly_preview, initialize_revision
from assemblies.models import AssemblyComponent, ComponentSourceType, Transform
from assemblies.store import AssemblyStore
from cad.generator import generate_step, generate_stl, generate_workplane
from cad.operation_validator import validate_operation_plan
from cad.validator import validate_part
from capabilities.invocation import CapabilityInvocationError, invoke_capability
from capabilities.registry import CapabilityRegistry
from engineering.analyzer import analyze_part
from engineering.geometry import calculate_geometry_metrics
from evaluation.baselines import compare_to_baseline, load_baseline, save_baseline
from evaluation.categories import BenchmarkCategory
from evaluation.fixtures import load_cases
from evaluation.metrics import calculate_metrics
from evaluation.models import (
    BenchmarkCase,
    BenchmarkDifficulty,
    BenchmarkMode,
    BenchmarkResult,
    BenchmarkStatus,
    EvaluationReport,
    FailureCategory,
    StageResult,
)
from evaluation.reporting import load_latest, write_reports
from projects.serialization import model_to_json, model_type_for
from projects.store import ProjectStore


DESIGN_ADAPTER = TypeAdapter(SupportedDesignSpec)
WORK_DIR = Path("outputs") / "evaluation" / "work"


def run_evaluation(
    *,
    suite: str = "full",
    category: BenchmarkCategory | str | None = None,
    difficulty: BenchmarkDifficulty | str | None = None,
    case_id: str | None = None,
    smoke: bool = False,
    update_baseline: bool = False,
    compare: bool = True,
    write: bool = True,
) -> EvaluationReport:
    cases = load_cases(category=category, difficulty=difficulty, case_id=case_id, smoke=smoke)
    _prepare_work_dir(WORK_DIR)
    results = [evaluate_case(case, WORK_DIR / case.case_id) for case in cases]
    report = EvaluationReport(
        suite=suite,
        generated_at=datetime.now(UTC).isoformat(),
        case_count=len(results),
        filters={
            "category": str(category) if category else None,
            "difficulty": str(difficulty) if difficulty else None,
            "case_id": case_id,
            "smoke": smoke,
        },
        metrics=calculate_metrics(results),
        results=results,
    )
    if compare:
        report.regressions = compare_to_baseline(report, load_baseline())
    if write:
        write_reports(report)
    if update_baseline:
        save_baseline(report)
    return report


def evaluate_case(case: BenchmarkCase, work_dir: Path) -> BenchmarkResult:
    started_at = datetime.now(UTC).isoformat()
    started = time.perf_counter()
    work_dir.mkdir(parents=True, exist_ok=True)
    stages: list[StageResult] = []
    metrics: dict[str, Any] = {"expected_exports": case.expected_export_formats}
    failure_category: FailureCategory | None = None
    failure_message: str | None = None
    model: SupportedDesignSpec | None = None
    generated = None

    def fail(category: FailureCategory, message: str) -> None:
        nonlocal failure_category, failure_message
        if failure_category is None:
            failure_category = category
            failure_message = message

    if case.expected_status == BenchmarkStatus.UNSUPPORTED:
        stages.append(StageResult(name="prompt_interpretation", success=True, message="Cleanly classified as unsupported."))
        duration = _elapsed_ms(started)
        return _result(case, started_at, duration, stages, metrics, BenchmarkStatus.UNSUPPORTED, FailureCategory.EXPECTED_UNSUPPORTED, case.notes)
    if case.expected_failure_category == FailureCategory.EXPECTED_AMBIGUITY:
        stages.append(StageResult(name="prompt_interpretation", success=True, message="Cleanly classified as expected ambiguity."))
        duration = _elapsed_ms(started)
        return _result(case, started_at, duration, stages, metrics, BenchmarkStatus.SKIPPED, FailureCategory.EXPECTED_AMBIGUITY, case.notes)

    ok, message = _stage(stages, "prompt_interpretation", lambda: _fixture_available(case))
    if not ok:
        fail(FailureCategory.PARSER, message or "No deterministic fixture was available.")
    if ok and case.fixture_spec is not None:
        ok, message, model = _stage_value(stages, "schema_validation", lambda: DESIGN_ADAPTER.validate_python(case.fixture_spec))
        if not ok:
            fail(FailureCategory.SCHEMA_VALIDATION, message or "Schema validation failed.")
    elif case.mode == BenchmarkMode.ASSEMBLY:
        stages.append(StageResult(name="schema_validation", success=True, message="Assembly fixture schema validated."))
    elif case.mode == BenchmarkMode.CAPABILITY:
        stages.append(StageResult(name="schema_validation", success=True, message="Capability fixture schema validated."))

    if model is not None:
        ok, message, model = _stage_value(stages, "design_intent_resolution", lambda: _resolve_model(model))
        if not ok:
            fail(FailureCategory.PARAMETRIC_RESOLUTION, message or "Parametric resolution failed.")

    if model is not None and isinstance(model, OperationPlan):
        ok, message = _stage(stages, "operation_validation", lambda: validate_operation_plan(model))
        if not ok:
            fail(FailureCategory.CAD_VALIDATION, message or "Operation validation failed.")
    elif model is not None:
        ok, message = _stage(stages, "cad_validation", lambda: validate_part(model))  # type: ignore[arg-type]
        if not ok:
            fail(FailureCategory.CAD_VALIDATION, message or "CAD validation failed.")

    if failure_category is None and model is not None:
        ok, message, generated = _stage_value(stages, "cad_execution", lambda: generate_workplane(model))
        if not ok:
            fail(FailureCategory.CAD_GENERATION, message or "CAD generation failed.")

    if generated is not None:
        ok, message, geometry = _stage_value(stages, "solid_validation", lambda: calculate_geometry_metrics(generated))
        if not ok:
            fail(FailureCategory.SOLID_VALIDATION, message or "Solid validation failed.")
        elif geometry is not None:
            metrics["geometry"] = geometry.model_dump(mode="json")
            geom_ok, geom_message = _check_geometry(case, geometry)
            stages.append(StageResult(name="geometric_expectations", success=geom_ok, message=geom_message))
            if not geom_ok:
                fail(FailureCategory.GEOMETRY_MISMATCH, geom_message or "Geometry expectation mismatch.")

    if failure_category is None and model is not None:
        structure_ok, structure_message = _check_structure(case, model)
        stages.append(StageResult(name="structural_expectations", success=structure_ok, message=structure_message))
        if not structure_ok:
            fail(FailureCategory.STRUCTURE_MISMATCH, structure_message or "Structure expectation mismatch.")

    if failure_category is None and model is not None:
        _run_exports(case, model, work_dir, stages, metrics, fail)
        _run_engineering(case, model, stages, metrics, fail)

    if case.mode == BenchmarkMode.ASSEMBLY and failure_category is None:
        _run_assembly(case, work_dir, stages, metrics, fail)
    if case.mode == BenchmarkMode.CAPABILITY and failure_category is None:
        _run_capability(case, work_dir, stages, metrics, fail)

    repair_attempted = False
    repair_success = False
    if failure_category is not None and case.repair_fixture_spec is not None:
        repair_attempted = True
        ok, message = _stage(stages, "repair", lambda: generate_workplane(DESIGN_ADAPTER.validate_python(case.repair_fixture_spec)))
        repair_success = ok
        if ok:
            failure_category = None
            failure_message = None
        else:
            fail(FailureCategory.REPAIR_FAILURE, message or "Repair failed.")

    status = _status(case, failure_category)
    duration = _elapsed_ms(started)
    result = _result(case, started_at, duration, stages, metrics, status, failure_category, failure_message)
    result.repair_attempted = repair_attempted
    result.repair_success = repair_success
    _derive_flags(result)
    return result


def latest_report() -> EvaluationReport | None:
    return load_latest()


def cases_for_api() -> list[BenchmarkCase]:
    return load_cases()


def run_live_evaluation(*, limit: int = 1, category: str | None = None, case_id: str | None = None, runs: int = 1) -> EvaluationReport:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for NON-DETERMINISTIC LIVE AI EVALUATION.")
    cases = load_cases(category=category, case_id=case_id)[: max(0, limit)]
    results = []
    for _ in range(max(1, runs)):
        for case in cases:
            results.append(evaluate_case(case, WORK_DIR / "live" / case.case_id))
    report = EvaluationReport(
        suite="live",
        generated_at=datetime.now(UTC).isoformat(),
        deterministic=False,
        live_ai=True,
        case_count=len(results),
        filters={"limit": limit, "category": category, "case_id": case_id, "runs": runs},
        metrics=calculate_metrics(results),
        results=results,
    )
    report_dir = Path("outputs") / "evaluation" / "live"
    write_reports(report, report_dir=report_dir)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation.runner")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run")
    run.add_argument("--category")
    run.add_argument("--difficulty")
    run.add_argument("--case")
    run.add_argument("--update-baseline", action="store_true")
    smoke = sub.add_parser("smoke")
    smoke.add_argument("--update-baseline", action="store_true")
    sub.add_parser("compare")
    sub.add_parser("report")
    sub.add_parser("update-baseline")
    live = sub.add_parser("live")
    live.add_argument("--limit", type=int, default=1)
    live.add_argument("--category")
    live.add_argument("--case")
    live.add_argument("--runs", type=int, default=1)
    args = parser.parse_args(argv)

    if args.command in {None, "run"}:
        report = run_evaluation(category=args.category, difficulty=args.difficulty, case_id=args.case, update_baseline=args.update_baseline)
        _print_summary(report)
        return 1 if report.metrics.fail_count or report.regressions else 0
    if args.command == "smoke":
        report = run_evaluation(suite="smoke", smoke=True, update_baseline=args.update_baseline)
        _print_summary(report)
        return 1 if report.metrics.fail_count or report.regressions else 0
    if args.command == "compare":
        report = load_latest()
        if report is None:
            print("No latest evaluation report found.")
            return 1
        report.regressions = compare_to_baseline(report, load_baseline())
        write_reports(report)
        _print_summary(report)
        return 1 if report.regressions else 0
    if args.command == "report":
        report = load_latest()
        if report is None:
            print("No latest evaluation report found.")
            return 1
        _print_summary(report)
        return 0
    if args.command == "update-baseline":
        report = load_latest()
        if report is None:
            report = run_evaluation(compare=False, write=True)
        save_baseline(report)
        print("Baseline updated.")
        return 0
    if args.command == "live":
        report = run_live_evaluation(limit=args.limit, category=args.category, case_id=args.case, runs=args.runs)
        _print_summary(report)
        return 0
    return 1


def _fixture_available(case: BenchmarkCase) -> None:
    if case.fixture_spec is None and case.mode not in {BenchmarkMode.ASSEMBLY, BenchmarkMode.CAPABILITY}:
        raise ValueError("Case has no fixture_spec.")


def _resolve_model(model: SupportedDesignSpec) -> SupportedDesignSpec:
    from parametrics.resolver import resolved_model

    return resolved_model(model)


def _run_exports(case: BenchmarkCase, model: SupportedDesignSpec, work_dir: Path, stages: list[StageResult], metrics: dict[str, Any], fail: Callable[[FailureCategory, str], None]) -> None:
    if "step" in case.expected_export_formats:
        path = work_dir / f"{case.case_id}.step"
        ok, message = _stage(stages, "step_export", lambda: generate_step(model, path))
        metrics["step_path"] = str(path) if ok else None
        if not ok:
            fail(FailureCategory.EXPORT_FAILURE, message or "STEP export failed.")
    if "stl" in case.expected_export_formats:
        path = work_dir / f"{case.case_id}.stl"
        ok, message = _stage(stages, "stl_export", lambda: generate_stl(model, path))
        metrics["stl_path"] = str(path) if ok else None
        if not ok:
            fail(FailureCategory.EXPORT_FAILURE, message or "STL export failed.")


def _run_engineering(case: BenchmarkCase, model: SupportedDesignSpec, stages: list[StageResult], metrics: dict[str, Any], fail: Callable[[FailureCategory, str], None]) -> None:
    expectation = case.engineering_expectation
    ok, message, report = _stage_value(
        stages,
        "engineering_analysis",
        lambda: analyze_part(model, material_id=expectation.material_id, display_units=expectation.display_units),
    )
    if not ok:
        fail(FailureCategory.ENGINEERING_FAILURE, message or "Engineering analysis failed.")
        return
    if report is None:
        return
    metrics["engineering"] = {
        "volume_mm3": report.geometry_metrics.volume_mm3,
        "warnings": [warning.category for warning in report.warnings],
        "mass_g": report.mass_estimate.mass_g if report.mass_estimate else None,
    }
    if expectation.mass_min_g is not None and (report.mass_estimate is None or report.mass_estimate.mass_g < expectation.mass_min_g):
        fail(FailureCategory.ENGINEERING_FAILURE, "Mass estimate is below expected range.")
    if expectation.mass_max_g is not None and (report.mass_estimate is None or report.mass_estimate.mass_g > expectation.mass_max_g):
        fail(FailureCategory.ENGINEERING_FAILURE, "Mass estimate is above expected range.")


def _run_assembly(case: BenchmarkCase, work_dir: Path, stages: list[StageResult], metrics: dict[str, Any], fail: Callable[[FailureCategory, str], None]) -> None:
    if case.assembly_fixture is None:
        fail(FailureCategory.ASSEMBLY_FAILURE, "Missing assembly fixture.")
        return
    isolated = work_dir / "isolated"
    isolated.mkdir(parents=True, exist_ok=True)
    project_store = ProjectStore(isolated / "projects.db")
    assembly_store = AssemblyStore(isolated / "assemblies.db")
    component_records: list[AssemblyComponent] = []
    for index, component in enumerate(case.assembly_fixture.components, start=1):
        model = DESIGN_ADAPTER.validate_python(component["spec"])
        project = project_store.create_project(name=component["name"], source_prompt=case.prompt, model_type=model_type_for(model))
        step_path = isolated / f"{project.project_id}.step"
        generate_step(model, step_path)
        project_store.add_revision(
            project_id=project.project_id,
            parent_revision_id=None,
            user_instruction="Evaluation assembly component",
            model_type=model_type_for(model),
            structured_spec_json=model_to_json(model),
            change_summary="Evaluation component",
            step_output_path=str(step_path),
        )
        transform_data = component.get("transform", {})
        component_records.append(
            AssemblyComponent(
                component_id=f"component_{index}",
                name=component["name"],
                source_type=ComponentSourceType.PROJECT_REVISION,
                project_id=project.project_id,
                project_revision=1,
                transform=Transform(**transform_data),
                grounded=bool(component.get("grounded", False)),
            )
        )
    assembly = assembly_store.create_assembly(name=case.name)
    revision = initialize_revision(assembly_id=assembly.assembly_id, components=component_records, store=assembly_store, project_store=project_store)
    preview = assembly_preview(assembly_id=assembly.assembly_id, revision_number=revision.revision_number, store=assembly_store, project_store=project_store)
    engineering = assembly_engineering(assembly_id=assembly.assembly_id, revision_number=revision.revision_number, store=assembly_store, project_store=project_store)
    metrics["assembly"] = {
        "component_count": engineering.component_count,
        "known_mass_g": engineering.known_mass_g,
        "interference_count": len(engineering.interferences),
        "bbox": preview.bounding_box.model_dump(mode="json") if preview.bounding_box else None,
    }
    expected_interference = case.assembly_fixture.expect_interference
    if expected_interference is not None and bool(engineering.interferences) != expected_interference:
        fail(FailureCategory.ASSEMBLY_FAILURE, "Assembly interference expectation mismatch.")
    stages.append(StageResult(name="assembly_analysis", success=True))


def _run_capability(case: BenchmarkCase, work_dir: Path, stages: list[StageResult], metrics: dict[str, Any], fail: Callable[[FailureCategory, str], None]) -> None:
    fixture = case.capability_fixture
    if fixture is None:
        fail(FailureCategory.CAPABILITY_FAILURE, "Missing capability fixture.")
        return
    registry = CapabilityRegistry((work_dir / "capabilities.json").resolve())
    try:
        registry.discover("local_adapters")
        with _pushd(work_dir):
            record = registry.run_self_test(fixture.capability_id)
            if fixture.enable_before_invoke:
                registry.approve(record.capability_id)
                registry.enable(record.capability_id)
            response = invoke_capability(fixture.capability_id, fixture.arguments, registry=registry)
        metrics["capability"] = response.result
        stages.append(StageResult(name="capability_invocation", success=True))
    except CapabilityInvocationError as exc:
        stages.append(StageResult(name="capability_invocation", success=not fixture.expect_success, message=str(exc)))
        if fixture.expect_success:
            fail(FailureCategory.CAPABILITY_FAILURE, str(exc))
    except Exception as exc:
        stages.append(StageResult(name="capability_invocation", success=False, message=str(exc)))
        fail(FailureCategory.CAPABILITY_FAILURE, str(exc))


def _check_structure(case: BenchmarkCase, model: SupportedDesignSpec) -> tuple[bool, str | None]:
    expectation = case.structural_expectation
    if case.expected_part_type and getattr(model, "part_type", None) != case.expected_part_type:
        return False, f"Expected part_type {case.expected_part_type}, got {getattr(model, 'part_type', None)}."
    if expectation.part_type and getattr(model, "part_type", None) != expectation.part_type:
        return False, f"Expected part_type {expectation.part_type}, got {getattr(model, 'part_type', None)}."
    operations = getattr(model, "operations", [])
    operation_types = [operation.operation_type for operation in operations]
    for operation_type in [*case.expected_operation_types, *expectation.operation_types]:
        if operation_type not in operation_types:
            return False, f"Missing operation type {operation_type}."
    if expectation.min_operation_count is not None and len(operation_types) < expectation.min_operation_count:
        return False, f"Expected at least {expectation.min_operation_count} operations, got {len(operation_types)}."
    parameters = {parameter.parameter_id: parameter.value for parameter in getattr(model, "parameters", [])}
    for key, expected in {**case.expected_parameters, **expectation.parameters}.items():
        if key not in parameters:
            return False, f"Missing parameter {key}."
        if abs(parameters[key] - expected) > 0.001:
            return False, f"Parameter {key} expected {expected}, got {parameters[key]}."
    return True, None


def _check_geometry(case: BenchmarkCase, geometry: Any) -> tuple[bool, str | None]:
    expectation = case.geometric_expectation
    if expectation.solid_count is not None and geometry.solid_count != expectation.solid_count:
        return False, f"Expected {expectation.solid_count} solids, got {geometry.solid_count}."
    if expectation.volume_min_mm3 is not None and geometry.volume_mm3 < expectation.volume_min_mm3:
        return False, "Volume below expected range."
    if expectation.volume_max_mm3 is not None and geometry.volume_mm3 > expectation.volume_max_mm3:
        return False, "Volume above expected range."
    bbox_values = {
        "x": geometry.size.x_mm,
        "y": geometry.size.y_mm,
        "z": geometry.size.z_mm,
    }
    for axis, expected in expectation.bbox.items():
        actual = bbox_values[axis]
        if abs(actual - expected) > expectation.bbox_tolerance_mm:
            return False, f"BBox {axis} expected {expected}, got {actual}."
    return True, None


def _status(case: BenchmarkCase, failure_category: FailureCategory | None) -> BenchmarkStatus:
    if case.expected_status in {BenchmarkStatus.UNSUPPORTED, BenchmarkStatus.SKIPPED}:
        return case.expected_status
    if failure_category is None:
        return BenchmarkStatus.PASS
    if case.expected_failure_category and failure_category == case.expected_failure_category:
        return BenchmarkStatus.PASS
    return BenchmarkStatus.FAIL


def _result(
    case: BenchmarkCase,
    started_at: str,
    duration_ms: int,
    stages: list[StageResult],
    metrics: dict[str, Any],
    status: BenchmarkStatus,
    failure_category: FailureCategory | None,
    failure_message: str | None,
) -> BenchmarkResult:
    result = BenchmarkResult(
        case_id=case.case_id,
        name=case.name,
        category=case.category,
        difficulty=case.difficulty,
        mode=case.mode,
        started_at=started_at,
        duration_ms=duration_ms,
        metrics=metrics,
        stages=stages,
        overall_status=status,
        failure_category=failure_category,
        failure_message=failure_message,
    )
    _derive_flags(result)
    return result


def _derive_flags(result: BenchmarkResult) -> None:
    by_name = {stage.name: stage for stage in result.stages}
    result.parse_success = by_name.get("prompt_interpretation", StageResult(name="", success=False)).success
    result.schema_validation_success = by_name.get("schema_validation", StageResult(name="", success=False)).success
    result.parametric_resolution_success = by_name.get("design_intent_resolution", StageResult(name="", success=False)).success
    result.cad_validation_success = (
        by_name.get("cad_validation", by_name.get("operation_validation", StageResult(name="", success=False))).success
    )
    result.cad_generation_success = by_name.get("cad_execution", StageResult(name="", success=False)).success
    result.solid_validation_success = by_name.get("solid_validation", StageResult(name="", success=False)).success
    result.step_export_success = by_name.get("step_export", StageResult(name="", success=False)).success
    result.stl_export_success = by_name.get("stl_export", StageResult(name="", success=False)).success
    result.expected_structure_match = by_name.get("structural_expectations", StageResult(name="", success=False)).success
    result.engineering_analysis_success = by_name.get("engineering_analysis", StageResult(name="", success=False)).success


def _stage(stages: list[StageResult], name: str, action: Callable[[], Any]) -> tuple[bool, str | None]:
    started = time.perf_counter()
    try:
        action()
        stages.append(StageResult(name=name, success=True, duration_ms=_elapsed_ms(started)))
        return True, None
    except Exception as exc:
        stages.append(StageResult(name=name, success=False, duration_ms=_elapsed_ms(started), message=str(exc)))
        return False, str(exc)


def _stage_value(stages: list[StageResult], name: str, action: Callable[[], Any]) -> tuple[bool, str | None, Any]:
    started = time.perf_counter()
    try:
        value = action()
        stages.append(StageResult(name=name, success=True, duration_ms=_elapsed_ms(started)))
        return True, None, value
    except Exception as exc:
        stages.append(StageResult(name=name, success=False, duration_ms=_elapsed_ms(started), message=str(exc)))
        return False, str(exc), None


def _prepare_work_dir(path: Path) -> None:
    root = (Path("outputs") / "evaluation").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Evaluation work directory must stay under outputs/evaluation.") from exc
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    path.mkdir(parents=True, exist_ok=True)
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _print_summary(report: EvaluationReport) -> None:
    print("SHAH INDUSTRIES EVALUATION")
    print(f"Suite: {report.suite}")
    print(f"Cases: {report.metrics.total_cases}")
    print(f"Passed: {report.metrics.pass_count}")
    print(f"Failed: {report.metrics.fail_count}")
    print(f"Unsupported: {report.metrics.unsupported_count}")
    print(f"Regressions: {len(report.regressions)}")
    print("JSON: outputs/evaluation/latest.json")
    print("Markdown: outputs/evaluation/latest.md")


if __name__ == "__main__":
    raise SystemExit(main())
