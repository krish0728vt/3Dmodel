from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

from ai.schemas import (
    BoxSpec,
    CylinderSpec,
    ElectronicsEnclosureSpec,
    HoleSpec,
    LBracketSpec,
    MountingPlateSpec,
    MountingPostSpec,
    OperationPlan,
    SpacerSpec,
    SupportedDesignSpec,
    SupportedPartSpec,
)
from ai.parser import (
    AIConnectionError,
    MalformedAIResponseError,
    MissingApiKeyError,
    MissingInformationError,
    UnsupportedPartError,
    parse_prompt,
)
from ai.editor import (
    AmbiguousEditError,
    EditParserError,
    UnsupportedEditError,
    parse_edit_request,
)

logging.getLogger("fontTools").setLevel(logging.ERROR)

from cad.generator import DEFAULT_OUTPUT_PATH, generate_step
from cad.operation_validator import OperationValidationError, validate_operation_plan
from cad.validator import GeometryValidationError
from capabilities.registry import CapabilityRegistry
from config import CONFIG
from assemblies.store import AssemblyStore
from exports.manager import ExportError, run_export
from exports.models import ExportFormat, ExportOptions, ExportRequest, ExportSourceType, StlQuality
from exports.store import ExportStore
from learning.classifier import classify_failure
from learning.adaptive import ENGINE_SCHEMA_VERSION
from learning.models import EvidenceStatus
from learning.repair import create_regression_candidate
from learning.retrieval import get_relevant_lessons
from learning.store import LearningStore
from projects.diff import diff_revisions
from projects.editor import EditApplicationError, apply_edit, apply_edit_to_project
from projects.manager import create_project_from_model
from projects.models import EditInstruction
from projects.revisions import export_revision, redo, restore, undo
from projects.serialization import model_from_json
from projects.store import ProjectStore
from pydantic import ValidationError
from pydantic import TypeAdapter


EDIT_ADAPTER = TypeAdapter(EditInstruction)


def _read_float(prompt: str) -> float:
    while True:
        raw_value = input(prompt).strip()
        try:
            return float(raw_value)
        except ValueError:
            print("Enter a numeric value in millimeters.")


def _read_choice(valid_choices: set[str]) -> str:
    while True:
        choice = input("> ").strip()
        if choice in valid_choices:
            return choice
        print(f"Choose one of: {', '.join(sorted(valid_choices))}.")


def _confirm(prompt: str) -> bool:
    response = input(prompt).strip().lower()
    return response in {"", "y", "yes"}


def create_symmetric_four_hole_plate(
    width_mm: float,
    height_mm: float,
    thickness_mm: float,
    corner_radius_mm: float,
    hole_diameter_mm: float,
    x_edge_offset_mm: float,
    y_edge_offset_mm: float,
) -> MountingPlateSpec:
    x = width_mm / 2 - x_edge_offset_mm
    y = height_mm / 2 - y_edge_offset_mm

    return MountingPlateSpec(
        width_mm=width_mm,
        height_mm=height_mm,
        thickness_mm=thickness_mm,
        corner_radius_mm=corner_radius_mm,
        holes=[
            HoleSpec(diameter_mm=hole_diameter_mm, x_mm=-x, y_mm=-y),
            HoleSpec(diameter_mm=hole_diameter_mm, x_mm=x, y_mm=-y),
            HoleSpec(diameter_mm=hole_diameter_mm, x_mm=-x, y_mm=y),
            HoleSpec(diameter_mm=hole_diameter_mm, x_mm=x, y_mm=y),
        ],
    )


def _print_banner() -> None:
    line = "=" * 50
    print(line)
    print("SHAH INDUSTRIES")
    print("AI CAD GENERATOR")
    print(line)
    print()


def _display_spec(spec: SupportedDesignSpec) -> None:
    print("INTERPRETED DESIGN")
    print()
    if isinstance(spec, OperationPlan):
        print("Operation Plan:")
        print(spec.project_name)
        print()
    else:
        print("Part:")
        print(_part_label(spec))
        print()
    for label, value in _spec_summary_lines(spec):
        print(label)
        print(value)
        print()


def _part_label(spec: SupportedPartSpec) -> str:
    labels = {
        "mounting_plate": "Mounting Plate",
        "box": "Box",
        "cylinder": "Cylinder",
        "spacer": "Spacer",
        "l_bracket": "L Bracket",
        "electronics_enclosure": "Electronics Enclosure",
    }
    return labels[spec.part_type]


def _spec_summary_lines(spec: SupportedDesignSpec) -> list[tuple[str, str]]:
    if isinstance(spec, OperationPlan):
        lines = [
            ("Units:", spec.units),
            ("Operations:", "\n".join(_operation_summary(index, operation) for index, operation in enumerate(spec.operations, start=1))),
            ("Final Object:", spec.final_object_id or spec.operations[-1].id),
        ]
        return lines
    if isinstance(spec, MountingPlateSpec):
        holes = "None"
        positions = "None"
        if spec.holes:
            holes = f"{len(spec.holes)} x diameter {spec.holes[0].diameter_mm:g} mm"
            positions = "\n".join(f"({hole.x_mm:g}, {hole.y_mm:g})" for hole in spec.holes)
        return [
            ("Width:", f"{spec.width_mm:g} mm"),
            ("Height:", f"{spec.height_mm:g} mm"),
            ("Thickness:", f"{spec.thickness_mm:g} mm"),
            ("Corner Radius:", f"{spec.corner_radius_mm:g} mm"),
            ("Holes:", holes),
            ("Positions:", positions),
        ]
    if isinstance(spec, BoxSpec):
        return [
            ("Width:", f"{spec.width_mm:g} mm"),
            ("Depth:", f"{spec.depth_mm:g} mm"),
            ("Height:", f"{spec.height_mm:g} mm"),
            ("Corner Radius:", f"{spec.corner_radius_mm:g} mm"),
        ]
    if isinstance(spec, CylinderSpec):
        center_hole = (
            f"{spec.center_hole_diameter_mm:g} mm"
            if spec.center_hole_diameter_mm is not None
            else "None"
        )
        return [
            ("Diameter:", f"{spec.diameter_mm:g} mm"),
            ("Height:", f"{spec.height_mm:g} mm"),
            ("Center Hole:", center_hole),
        ]
    if isinstance(spec, SpacerSpec):
        return [
            ("Outer Diameter:", f"{spec.outer_diameter_mm:g} mm"),
            ("Inner Diameter:", f"{spec.inner_diameter_mm:g} mm"),
            ("Height:", f"{spec.height_mm:g} mm"),
        ]
    if isinstance(spec, LBracketSpec):
        return [
            ("Width:", f"{spec.width_mm:g} mm"),
            ("Height:", f"{spec.height_mm:g} mm"),
            ("Leg Depth:", f"{spec.leg_depth_mm:g} mm"),
            ("Thickness:", f"{spec.thickness_mm:g} mm"),
            ("Corner Radius:", f"{spec.corner_radius_mm:g} mm"),
            ("Holes:", "Not supported for L brackets in this milestone"),
        ]
    if isinstance(spec, ElectronicsEnclosureSpec):
        posts = "None"
        if spec.mounting_posts:
            posts = "\n".join(
                (
                    f"({post.x_mm:g}, {post.y_mm:g}) "
                    f"OD {post.outer_diameter_mm:g} mm, hole {post.hole_diameter_mm:g} mm, "
                    f"height {post.height_mm:g} mm"
                )
                for post in spec.mounting_posts
            )
        return [
            ("Internal Width:", f"{spec.internal_width_mm:g} mm"),
            ("Internal Depth:", f"{spec.internal_depth_mm:g} mm"),
            ("Internal Height:", f"{spec.internal_height_mm:g} mm"),
            ("Wall Thickness:", f"{spec.wall_thickness_mm:g} mm"),
            ("Bottom Thickness:", f"{spec.bottom_thickness_mm:g} mm"),
            ("Corner Radius:", f"{spec.corner_radius_mm:g} mm"),
            ("Mounting Posts:", posts),
        ]
    raise TypeError(f"Unsupported part specification: {type(spec).__name__}")
    print()


def _operation_summary(index: int, operation: object) -> str:
    operation_type = getattr(operation, "operation_type", type(operation).__name__)
    operation_id = getattr(operation, "id", "unknown")
    details: list[str] = []
    for field_name, value in operation.model_dump().items():
        if field_name in {"id", "operation_type"}:
            continue
        details.append(f"{field_name}={value}")
    detail_text = ", ".join(details)
    if detail_text:
        return f"Operation {index}: {operation_type} ({operation_id}) - {detail_text}"
    return f"Operation {index}: {operation_type} ({operation_id})"


def _generate_confirmed_model(spec: SupportedDesignSpec) -> Path | None:
    _display_spec(spec)
    if not _confirm("Generate this model? [Y/n] "):
        print()
        print("Generation cancelled.")
        return None

    try:
        return generate_step(spec, DEFAULT_OUTPUT_PATH)
    except Exception as exc:
        _record_generation_failure(spec=spec, exc=exc)
        raise


def _record_generation_failure(spec: SupportedDesignSpec, exc: BaseException) -> None:
    if not CONFIG.learning_enabled:
        return
    try:
        store = LearningStore()
        store.record_failure(
            error_category=classify_failure(exc),
            error_message=str(exc),
            parsed_spec_json=None if isinstance(spec, OperationPlan) else spec.model_dump_json(),
            operation_plan_json=spec.model_dump_json() if isinstance(spec, OperationPlan) else None,
        )
    except Exception:
        pass


def _natural_language_mode() -> int:
    print("Describe the part you want to create:")
    print()
    prompt = input("> ")
    print()

    try:
        spec = parse_prompt(prompt)
        output_path = _generate_confirmed_model(spec)
    except (
        AIConnectionError,
        GeometryValidationError,
        MalformedAIResponseError,
        MissingApiKeyError,
        MissingInformationError,
        OperationValidationError,
        UnsupportedPartError,
    ) as exc:
        print(exc)
        return 1

    if output_path is None:
        return 0

    _print_success(spec, output_path)
    _offer_save_project(spec, "Natural-language model", prompt)
    return 0


def _manual_mode() -> int:
    print("Choose a part type:")
    print("1. Mounting plate")
    print("2. Box")
    print("3. Cylinder")
    print("4. Spacer")
    print("5. L bracket")
    print("6. Electronics enclosure")
    print()
    part_choice = _read_choice({"1", "2", "3", "4", "5", "6"})
    print()

    try:
        spec = _read_manual_spec(part_choice)
        output_path = _generate_confirmed_model(spec)
    except GeometryValidationError as exc:
        print()
        print(exc)
        return 1

    if output_path is None:
        return 0

    _print_success(spec, output_path)
    _offer_save_project(spec, _part_label(spec), "Manual model")
    return 0


def _read_manual_spec(part_choice: str) -> SupportedPartSpec:
    if part_choice == "1":
        return _read_mounting_plate_spec()
    if part_choice == "2":
        return BoxSpec(
            width_mm=_read_float("Box width in mm: "),
            depth_mm=_read_float("Box depth in mm: "),
            height_mm=_read_float("Box height in mm: "),
            corner_radius_mm=_read_float("Vertical corner radius in mm: "),
        )
    if part_choice == "3":
        diameter_mm = _read_float("Cylinder diameter in mm: ")
        height_mm = _read_float("Cylinder height in mm: ")
        center_hole = _read_float("Center hole diameter in mm (0 for none): ")
        return CylinderSpec(
            diameter_mm=diameter_mm,
            height_mm=height_mm,
            center_hole_diameter_mm=center_hole if center_hole > 0 else None,
        )
    if part_choice == "4":
        return SpacerSpec(
            outer_diameter_mm=_read_float("Spacer outer diameter in mm: "),
            inner_diameter_mm=_read_float("Spacer inner diameter in mm: "),
            height_mm=_read_float("Spacer height in mm: "),
        )
    if part_choice == "5":
        return LBracketSpec(
            width_mm=_read_float("L bracket width in mm: "),
            height_mm=_read_float("L bracket height in mm: "),
            leg_depth_mm=_read_float("L bracket leg depth in mm: "),
            thickness_mm=_read_float("L bracket thickness in mm: "),
            corner_radius_mm=_read_float("Corner radius in mm: "),
        )
    return _read_enclosure_spec()


def _read_mounting_plate_spec() -> MountingPlateSpec:
    width_mm = _read_float("Plate width in mm: ")
    height_mm = _read_float("Plate height in mm: ")
    thickness_mm = _read_float("Plate thickness in mm: ")
    corner_radius_mm = _read_float("Corner radius in mm: ")
    hole_diameter_mm = _read_float("Hole diameter in mm: ")
    x_edge_offset_mm = _read_float("Hole X offset from left/right edges in mm: ")
    y_edge_offset_mm = _read_float("Hole Y offset from top/bottom edges in mm: ")

    return create_symmetric_four_hole_plate(
        width_mm=width_mm,
        height_mm=height_mm,
        thickness_mm=thickness_mm,
        corner_radius_mm=corner_radius_mm,
        hole_diameter_mm=hole_diameter_mm,
        x_edge_offset_mm=x_edge_offset_mm,
        y_edge_offset_mm=y_edge_offset_mm,
    )


def _read_enclosure_spec() -> ElectronicsEnclosureSpec:
    internal_width_mm = _read_float("Internal width in mm: ")
    internal_depth_mm = _read_float("Internal depth in mm: ")
    internal_height_mm = _read_float("Internal height in mm: ")
    wall_thickness_mm = _read_float("Wall thickness in mm: ")
    bottom_thickness_mm = _read_float("Bottom thickness in mm: ")
    corner_radius_mm = _read_float("Outer corner radius in mm: ")
    posts: list[MountingPostSpec] = []
    post_count = int(_read_float("Mounting post count (0 for none): "))
    for index in range(post_count):
        print(f"Mounting post {index + 1}:")
        posts.append(
            MountingPostSpec(
                x_mm=_read_float("  X position in mm: "),
                y_mm=_read_float("  Y position in mm: "),
                outer_diameter_mm=_read_float("  Outer diameter in mm: "),
                hole_diameter_mm=_read_float("  Hole diameter in mm: "),
                height_mm=_read_float("  Height in mm: "),
            )
        )
    return ElectronicsEnclosureSpec(
        internal_width_mm=internal_width_mm,
        internal_depth_mm=internal_depth_mm,
        internal_height_mm=internal_height_mm,
        wall_thickness_mm=wall_thickness_mm,
        bottom_thickness_mm=bottom_thickness_mm,
        corner_radius_mm=corner_radius_mm,
        mounting_posts=posts,
    )


def _print_success(spec: SupportedDesignSpec, output_path: Path) -> None:
    print()
    print("Model generated successfully.")
    print()
    if isinstance(spec, OperationPlan):
        print("Operation plan:")
        print(spec.project_name)
    else:
        print("Part:")
        print(_part_label(spec))
    print()
    for label, value in _spec_summary_lines(spec):
        print(label)
        print(value)
        print()
    print("Output:")
    print(output_path)


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    if argv and argv[0] == "project":
        return _project_cli(argv[1:])
    if argv and argv[0] == "learning":
        return _learning_cli(argv[1:])
    if argv and argv[0] == "capabilities":
        return _capabilities_cli(argv[1:])
    if argv and argv[0] == "export":
        return _export_cli(argv[1:])
    if argv and argv[0] == "assembly":
        return _assembly_cli(argv[1:])
    if argv and argv[0] == "evaluate":
        from evaluation.runner import main as evaluation_main

        return evaluation_main(argv[1:])
    if argv and argv[0] in _DEPLOYMENT_COMMANDS:
        return _deployment_cli(argv)

    parser = argparse.ArgumentParser(description="SHAH INDUSTRIES AI CAD GENERATOR")
    parser.add_argument("--plan", type=Path, help="Load and run a JSON operation plan.")
    args = parser.parse_args(argv)

    if args.plan is not None:
        return _run_plan_file(args.plan)

    _print_banner()
    print("1. Describe a part using natural language")
    print("2. Enter dimensions manually")
    print("3. Advanced operation plan")
    print()
    choice = _read_choice({"1", "2", "3"})
    print()

    if choice == "1":
        return _natural_language_mode()
    if choice == "2":
        return _manual_mode()
    return _advanced_operation_mode()


def _advanced_operation_mode() -> int:
    print("Advanced operation plan")
    print("1. Load JSON plan from file")
    print("2. Paste JSON plan")
    print()
    choice = _read_choice({"1", "2"})
    print()

    try:
        if choice == "1":
            path = Path(input("Plan file path: ").strip())
            plan = load_operation_plan(path)
        else:
            print("Paste a single-line JSON operation plan:")
            raw_json = input("> ")
            plan = parse_operation_plan_json(raw_json)
        output_path = _generate_confirmed_model(plan)
    except (OSError, OperationValidationError, ValidationError, ValueError) as exc:
        print(exc)
        return 1

    if output_path is None:
        return 0

    _print_success(plan, output_path)
    return 0


_DEPLOYMENT_COMMANDS = frozenset(
    {"serve", "setup", "doctor", "stop", "status", "version", "build", "clean", "backup"}
)


def _deployment_cli(argv: list[str]) -> int:
    """Local deployment commands. Imported lazily so the CAD CLI stays fast."""
    from deployment import bootstrap, checks, launcher
    from shah_version import version_line

    command = argv[0]
    rest = argv[1:]

    if command == "version":
        from shah_version import APP_VERSION, SCHEMA_VERSION

        print(version_line())
        print(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        print(f"Schema: {SCHEMA_VERSION}")
        _ = APP_VERSION
        return 0

    if command == "doctor":
        parser = argparse.ArgumentParser(prog="app.py doctor")
        parser.add_argument("--backend-port", type=int, default=8000)
        parser.add_argument("--frontend-port", type=int, default=5173)
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
        parser.add_argument(
            "--skip-frontend",
            action="store_true",
            help="Omit Node/npm/frontend checks (for backend-only environments).",
        )
        args = parser.parse_args(rest)
        report = checks.run_doctor(
            backend_port=args.backend_port,
            frontend_port=args.frontend_port,
            host=args.host,
            include_frontend=not args.skip_frontend,
        )
        if args.json:
            print(report.model_dump_json(indent=2))
        else:
            print(checks.format_report(report))
        return report.exit_code

    if command == "setup":
        parser = argparse.ArgumentParser(prog="app.py setup")
        parser.add_argument("--skip-python", action="store_true", help="Do not install Python packages.")
        parser.add_argument("--skip-frontend", action="store_true", help="Do not install npm packages.")
        parser.add_argument(
            "--repair-frontend",
            action="store_true",
            help="Remove web/node_modules before installing (explicit repair).",
        )
        args = parser.parse_args(rest)
        return bootstrap.run_setup(
            install_python=not args.skip_python,
            install_frontend=not args.skip_frontend,
            repair_frontend=args.repair_frontend,
        )

    if command == "serve":
        parser = argparse.ArgumentParser(prog="app.py serve")
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dev", action="store_true", help="FastAPI reload plus the Vite dev server.")
        mode.add_argument(
            "--production",
            action="store_true",
            help="Serve the built frontend from FastAPI on one port (default).",
        )
        parser.add_argument("--host", default=None, help="Bind address (default 127.0.0.1).")
        parser.add_argument("--backend-port", type=int, default=None)
        parser.add_argument("--frontend-port", type=int, default=None)
        parser.add_argument("--build", action="store_true", help="Build the frontend before serving.")
        parser.add_argument(
            "--auto-port",
            action="store_true",
            help="Use the next free port when the requested one is busy.",
        )
        parser.add_argument("--timeout", type=int, default=None, help="Health-check timeout in seconds.")
        browser = parser.add_mutually_exclusive_group()
        browser.add_argument("--open", dest="open_browser", action="store_true", default=None)
        browser.add_argument("--no-open", dest="open_browser", action="store_false", default=None)
        args = parser.parse_args(rest)
        launcher._install_sigterm_handler()
        return launcher.serve(
            dev=args.dev,
            host=args.host,
            backend_port=args.backend_port,
            frontend_port=args.frontend_port,
            open_browser=args.open_browser,
            auto_port=args.auto_port,
            build=args.build,
            timeout=args.timeout,
        )

    if command == "stop":
        return launcher.stop()

    if command == "status":
        return launcher.status()

    if command == "build":
        parser = argparse.ArgumentParser(prog="app.py build")
        parser.add_argument("--tests", action="store_true", help="Also run the frontend test suite.")
        parser.add_argument("--skip-typecheck", action="store_true")
        args = parser.parse_args(rest)
        return launcher.run_build(run_tests=args.tests, run_typecheck=not args.skip_typecheck)

    if command == "clean":
        parser = argparse.ArgumentParser(prog="app.py clean")
        parser.add_argument("--yes", action="store_true", help="Actually remove the listed artifacts.")
        args = parser.parse_args(rest)
        return launcher.clean(yes=args.yes)

    if command == "backup":
        return launcher.backup()

    return 1


def _project_cli(argv: list[str]) -> int:
    store = ProjectStore()
    command = argv[0] if argv else "list"
    if command == "list":
        for project in store.list_projects():
            print(
                f"{project.project_id} | {project.name} | current={project.current_revision} | "
                f"{project.model_type}"
            )
        return 0
    if command == "show" and len(argv) >= 2:
        project = store.get_project(argv[1])
        if project is None:
            print(f"Unknown project: {argv[1]}")
            return 1
        print(project.model_dump_json(indent=2))
        return 0
    if command == "rename" and len(argv) >= 3:
        try:
            project = store.rename_project(argv[1], " ".join(argv[2:]))
            print(f"Renamed project: {project.name}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "duplicate" and len(argv) >= 2:
        try:
            revision_number = _revision_arg(argv[2:])
            project, revision = store.duplicate_project(argv[1], revision_number=revision_number)
            print(f"Duplicated project: {project.project_id} rev {revision.revision_number}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "archive" and len(argv) >= 2:
        try:
            project = store.archive_project(argv[1])
            print(f"Archived project: {project.project_id}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "unarchive" and len(argv) >= 2:
        try:
            project = store.unarchive_project(argv[1])
            print(f"Unarchived project: {project.project_id}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "delete" and len(argv) >= 2:
        project = store.get_project(argv[1])
        if project is None:
            print(f"Unknown project: {argv[1]}")
            return 1
        print(f"This permanently deletes project '{project.name}' and generated project files.")
        confirmation = input("Type DELETE to continue: ").strip()
        if confirmation != "DELETE":
            print("Delete cancelled.")
            return 1
        try:
            result = store.delete_project(argv[1])
            print(f"Deleted project: {argv[1]} ({result['revision_count']} revisions, {result['file_count']} files)")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "history" and len(argv) >= 2:
        for revision in store.history(argv[1]):
            marker = "* " if store.get_project(argv[1]) and store.get_project(argv[1]).current_revision == revision.revision_number else "  "
            print(f"{marker}rev {revision.revision_number}: {revision.change_summary}")
        return 0
    if command == "edit" and len(argv) >= 2:
        return _project_edit_once(argv[1], store)
    if command == "chat" and len(argv) >= 2:
        return _project_chat(argv[1], store)
    if command == "undo" and len(argv) >= 2:
        try:
            revision = undo(argv[1], store=store)
            print(f"Current revision: {revision.revision_number}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "redo" and len(argv) >= 2:
        try:
            revision = redo(argv[1], store=store)
            print(f"Current revision: {revision.revision_number}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "restore" and len(argv) >= 3:
        try:
            revision = restore(argv[1], int(argv[2]), store=store)
            print(f"Restored revision: {revision.revision_number}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "diff" and len(argv) >= 4:
        try:
            print(diff_revisions(argv[1], int(argv[2]), int(argv[3]), store=store))
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "export" and len(argv) >= 2:
        revision_number = _revision_arg(argv[2:])
        try:
            path = export_revision(argv[1], revision_number, store=store)
            print(f"Exported: {path}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    print(
        "Usage: python app.py project "
        "[list|show <id>|rename <id> <name>|duplicate <id>|archive <id>|unarchive <id>|delete <id>|history <id>|edit <id>|chat <id>|undo <id>|redo <id>|"
        "restore <id> <rev>|diff <id> <a> <b>|export <id> [--revision n]]"
    )
    return 1


def _project_edit_once(project_id: str, store: ProjectStore) -> int:
    project = store.get_project(project_id)
    current = store.current_revision(project_id)
    if project is None or current is None:
        print(f"Unknown project or revision: {project_id}")
        return 1
    _print_conversational_banner(project, current.revision_number)
    instruction = input("> ").strip()
    return _apply_project_instruction(project_id, instruction, store)


def _project_chat(project_id: str, store: ProjectStore) -> int:
    project = store.get_project(project_id)
    current = store.current_revision(project_id)
    if project is None or current is None:
        print(f"Unknown project or revision: {project_id}")
        return 1
    _print_conversational_banner(project, current.revision_number)
    while True:
        instruction = input("> ").strip()
        if instruction.lower() in {"quit", "exit"}:
            return 0
        if instruction.lower() == "history":
            _project_cli(["history", project_id])
            continue
        if instruction.lower() == "export":
            _project_cli(["export", project_id])
            continue
        if instruction.lower() == "undo":
            _project_cli(["undo", project_id])
            continue
        if instruction.lower() == "redo":
            _project_cli(["redo", project_id])
            continue
        result = _apply_project_instruction(project_id, instruction, store)
        if result != 0:
            print("Edit was not applied.")


def _apply_project_instruction(project_id: str, instruction: str, store: ProjectStore) -> int:
    current = store.current_revision(project_id)
    if current is None:
        print("Project has no current revision.")
        return 1
    try:
        edit = _parse_edit_for_project(project_id, instruction, store)
        current_model = model_from_json(current.model_type, current.structured_spec_json)
        _, summary = apply_edit(current_model, edit)
        print()
        print("INTERPRETED CHANGE")
        print()
        print(summary)
        print()
        next_number = store.next_revision_number(project_id)
        if not _confirm(f"Create Revision {next_number}? [Y/n] "):
            print("Edit cancelled.")
            return 0
        revision, _ = apply_edit_to_project(
            project_id=project_id,
            edit=edit,
            user_instruction=instruction,
            store=store,
        )
        print(f"Created revision {revision.revision_number}.")
        return 0
    except (
        AmbiguousEditError,
        EditApplicationError,
        EditParserError,
        GeometryValidationError,
        OperationValidationError,
        UnsupportedEditError,
        ValidationError,
        ValueError,
    ) as exc:
        print(exc)
        return 1


def _parse_edit_for_project(project_id: str, instruction: str, store: ProjectStore) -> EditInstruction:
    if instruction.strip().startswith("{"):
        return EDIT_ADAPTER.validate_json(instruction)
    current = store.current_revision(project_id)
    if current is None:
        raise ValueError("Project has no current revision.")
    current_model = model_from_json(current.model_type, current.structured_spec_json)
    learning_store = LearningStore()
    lessons = get_relevant_lessons(store=learning_store, prompt=instruction, limit=5)
    capabilities = [cap.capability_id for cap in CapabilityRegistry().enabled_for_generation()]
    return parse_edit_request(
        instruction,
        current_model,
        relevant_lessons=[lesson.description for lesson in lessons],
        enabled_capabilities=capabilities,
        current_revision_number=current.revision_number,
    )


def _revision_arg(args: list[str]) -> int | None:
    if "--revision" in args:
        index = args.index("--revision")
        if index + 1 < len(args):
            return int(args[index + 1])
    return None


def _export_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python app.py export", description="Export project or assembly revisions.")
    parser.add_argument("source", choices=["project", "assembly", "capability", "package"])
    parser.add_argument("source_id")
    parser.add_argument("--revision", type=int)
    parser.add_argument("--format", nargs="+", default=["step"], help="Formats: step stl dxf manifest zip")
    parser.add_argument("--stl-quality", choices=["draft", "standard", "high"], default="standard")
    parser.add_argument("--package", action="store_true", help="Also generate a zip package.")
    args = parser.parse_args(argv)

    source_kind = "project" if args.source == "package" else args.source
    source_type = {
        "project": ExportSourceType.PROJECT_REVISION,
        "assembly": ExportSourceType.ASSEMBLY_REVISION,
        "capability": ExportSourceType.CAPABILITY_OUTPUT,
    }[source_kind]
    try:
        formats = [ExportFormat(item.lower()) for item in args.format]
        request = ExportRequest(
            source_type=source_type,
            source_id=args.source_id,
            revision=args.revision,
            formats=formats,
            options=ExportOptions(stl_quality=StlQuality(args.stl_quality), package=args.package or args.source == "package"),
        )
        batch = run_export(
            request,
            project_store=ProjectStore(),
            assembly_store=AssemblyStore(),
            export_store=ExportStore(),
        )
    except (ExportError, ValueError) as exc:
        print(exc)
        return 1

    print(f"Exported {batch.source_name} revision {batch.revision}:")
    for result in batch.results:
        print(f"{result.format.value.upper()} | {result.filename} | {result.size_bytes} bytes | SHA256 {result.checksum_sha256[:12]}")
    return 0


def _assembly_cli(argv: list[str]) -> int:
    store = AssemblyStore()
    command = argv[0] if argv else "list"
    if command == "list":
        for assembly in store.list_assemblies(status="all"):
            print(f"{assembly.assembly_id} | {assembly.name} | current={assembly.current_revision} | {assembly.status.value}")
        return 0
    if command == "rename" and len(argv) >= 3:
        try:
            assembly = store.rename_assembly(argv[1], " ".join(argv[2:]))
            print(f"Renamed assembly: {assembly.name}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "duplicate" and len(argv) >= 2:
        try:
            revision_number = _revision_arg(argv[2:])
            assembly, revision = store.duplicate_assembly(argv[1], revision_number=revision_number)
            print(f"Duplicated assembly: {assembly.assembly_id} rev {revision.revision_number}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "archive" and len(argv) >= 2:
        try:
            assembly = store.archive_assembly(argv[1])
            print(f"Archived assembly: {assembly.assembly_id}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "unarchive" and len(argv) >= 2:
        try:
            assembly = store.unarchive_assembly(argv[1])
            print(f"Unarchived assembly: {assembly.assembly_id}")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    if command == "delete" and len(argv) >= 2:
        assembly = store.get_assembly(argv[1])
        if assembly is None:
            print(f"Unknown assembly: {argv[1]}")
            return 1
        print(f"This permanently deletes assembly '{assembly.name}' and generated assembly files.")
        confirmation = input("Type DELETE to continue: ").strip()
        if confirmation != "DELETE":
            print("Delete cancelled.")
            return 1
        try:
            result = store.delete_assembly(argv[1])
            print(f"Deleted assembly: {argv[1]} ({result['revision_count']} revisions, {result['file_count']} files)")
            return 0
        except Exception as exc:
            print(exc)
            return 1
    print("Usage: python app.py assembly [list|rename <id> <name>|duplicate <id>|archive <id>|unarchive <id>|delete <id>]")
    return 1


def _print_conversational_banner(project: object, revision_number: int) -> None:
    line = "=" * 50
    print(line)
    print("SHAH INDUSTRIES")
    print("CONVERSATIONAL CAD")
    print(line)
    print()
    print("Project:")
    print(getattr(project, "name"))
    print()
    print("Current revision:")
    print(revision_number)
    print()


def _learning_cli(argv: list[str]) -> int:
    store = LearningStore()
    _print_learning_banner()
    command = argv[0] if argv else "stats"
    if command == "stats":
        stats = store.stats()
        print(f"Failures recorded: {stats['failures']}")
        print(f"Resolved: {stats['resolved']}")
        print(f"Lessons: {stats['lessons']}")
        print(f"Reusable patterns: {stats['patterns']}")
        print(f"Repair strategies: {stats['repair_strategies']}")
        print(f"Repair success rate: {stats['repair_success_rate']}%")
        return 0
    if command == "failures":
        for failure in store.list_failures():
            print(f"{failure.failure_id} | {failure.error_category.value} | resolved={failure.resolved}")
            print(f"  {failure.error_message}")
        return 0
    if command == "lessons":
        for lesson in store.list_lessons():
            print(f"{lesson.lesson_id} | {lesson.title} | confidence={lesson.confidence:g}")
        return 0
    if command == "patterns":
        for pattern in store.list_patterns():
            print(f"{pattern.pattern_id} | {pattern.name} | successes={pattern.success_count}")
        return 0
    if command == "strategies":
        for strategy in store.list_repair_strategies():
            print(
                f"{strategy.strategy_signature} | {strategy.status.value} | "
                f"confidence={strategy.confidence_score:g} | {strategy.successes}S/{strategy.failures}F"
            )
        return 0
    if command == "show" and len(argv) >= 2:
        identifier = argv[1]
        failure = store.get_failure(identifier)
        if failure:
            print(f"Failure: {failure.failure_id}")
            print(f"Category: {failure.error_category.value}")
            print(f"Resolved: {failure.resolved}")
            print(f"Error: {failure.error_message}")
            return 0
        lesson = store.get_lesson(identifier)
        if lesson:
            print(f"Lesson: {lesson.lesson_id}")
            print(lesson.title)
            print(lesson.description)
            return 0
        print(f"No learning record found for {identifier}.")
        return 1
    if command == "lesson" and len(argv) >= 3:
        action, lesson_id = argv[1], argv[2]
        lesson = store.get_lesson(lesson_id)
        if lesson is None:
            print(f"Unknown lesson: {lesson_id}")
            return 1
        if action == "show":
            print(lesson.model_dump_json(indent=2))
            return 0
        if action == "trust":
            print(store.set_lesson_status(lesson_id, EvidenceStatus.TRUSTED).model_dump_json(indent=2))
            return 0
        if action == "deprecate":
            print(store.set_lesson_status(lesson_id, EvidenceStatus.DEPRECATED).model_dump_json(indent=2))
            return 0
        if action == "revalidate":
            print(store.record_lesson_evidence(lesson_id, success=True).model_dump_json(indent=2))
            return 0
        if action == "history":
            print(lesson.model_dump_json(indent=2))
            return 0
    if command == "pattern" and len(argv) >= 3:
        action, pattern_id = argv[1], argv[2]
        pattern = store.get_pattern(pattern_id)
        if pattern is None:
            print(f"Unknown pattern: {pattern_id}")
            return 1
        if action == "show":
            print(pattern.model_dump_json(indent=2))
            return 0
        if action == "trust":
            print(store.set_pattern_status(pattern_id, EvidenceStatus.TRUSTED).model_dump_json(indent=2))
            return 0
        if action == "deprecate":
            print(store.set_pattern_status(pattern_id, EvidenceStatus.DEPRECATED).model_dump_json(indent=2))
            return 0
        if action == "revalidate":
            print(store.record_pattern_evidence(pattern_id, success=True).model_dump_json(indent=2))
            return 0
    if command == "revalidate":
        for lesson in store.list_lessons(limit=200):
            if lesson.status != EvidenceStatus.DEPRECATED:
                store.record_lesson_evidence(lesson.lesson_id, success=True)
        for pattern in store.list_patterns(limit=200):
            if pattern.status != EvidenceStatus.DEPRECATED:
                store.record_pattern_evidence(pattern.pattern_id, success=True)
        print("Revalidation pass recorded for active lessons and patterns.")
        return 0
    if command == "mark-stale":
        result = store.mark_records_needing_revalidation(engine_version=ENGINE_SCHEMA_VERSION)
        print(f"Marked stale: {result['lessons']} lessons, {result['patterns']} patterns.")
        return 0
    if command == "create-regression" and len(argv) >= 2:
        try:
            path = create_regression_candidate(store=store, failure_id=argv[1])
        except ValueError as exc:
            print(exc)
            return 1
        print(f"Candidate regression created: {path}")
        return 0
    print("Usage: python app.py learning [stats|failures|lessons|patterns|strategies|show <id>|lesson <show|trust|deprecate|revalidate|history> <id>|pattern <show|trust|deprecate|revalidate> <id>|revalidate|mark-stale|create-regression <failure_id>]")
    return 1


def _capabilities_cli(argv: list[str]) -> int:
    registry = CapabilityRegistry()
    command = argv[0] if argv else "list"
    if command == "sources":
        for source in registry.list_sources():
            print(
                f"{source.source_id} | {source.source_type.value} | "
                f"enabled={source.enabled} | trusted={source.trusted}"
            )
        return 0
    if command == "list":
        for capability in registry.list():
            print(
                f"{capability.capability_id} | {capability.trust_level.value} | "
                f"enabled={capability.enabled} | validation={capability.validation_status.value}"
            )
        return 0
    if command == "inspect" and len(argv) >= 2:
        capability = registry.get(argv[1])
        if capability is None:
            print(f"Unknown capability: {argv[1]}")
            return 1
        print(capability.model_dump_json(indent=2))
        return 0
    if command == "discover":
        try:
            if len(argv) >= 3 and argv[1] == "--source":
                capabilities = registry.discover(argv[2])
            elif len(argv) >= 2:
                capabilities = [registry.discover_manifest(argv[1])]
            else:
                capabilities = registry.discover()
        except Exception as exc:
            print(exc)
            return 1
        for capability in capabilities:
            print(f"Discovered capability: {capability.capability_id}")
        return 0
    if command == "test" and len(argv) >= 2:
        try:
            capability = registry.run_self_test(argv[1])
        except Exception as exc:
            print(exc)
            return 1
        print(f"{capability.capability_id}: {capability.validation_status.value}")
        return 0
    if command == "enable" and len(argv) >= 2:
        try:
            capability = registry.enable(argv[1])
        except Exception as exc:
            print(exc)
            return 1
        print(f"Enabled: {capability.capability_id}")
        return 0
    if command == "approve" and len(argv) >= 2:
        try:
            capability = registry.approve(argv[1])
        except Exception as exc:
            print(exc)
            return 1
        print(f"Approved: {capability.capability_id}")
        return 0
    if command == "disable" and len(argv) >= 2:
        try:
            capability = registry.disable(argv[1])
        except Exception as exc:
            print(exc)
            return 1
        print(f"Disabled: {capability.capability_id}")
        return 0
    if command == "invoke" and len(argv) >= 4 and argv[2] == "--input":
        try:
            from capabilities.invocation import invoke_capability

            response = invoke_capability(argv[1], json.loads(argv[3]), registry=registry, learning_store=LearningStore())
        except Exception as exc:
            print(exc)
            return 1
        print(response.model_dump_json(indent=2))
        return 0
    print(
        "Usage: python app.py capabilities "
        "[sources|list|inspect <id>|discover [<manifest>|--source <source_id>]|test <id>|approve <id>|enable <id>|disable <id>|invoke <id> --input <json>]"
    )
    return 1


def _print_learning_banner() -> None:
    line = "=" * 50
    print(line)
    print("SHAH INDUSTRIES")
    print("LEARNING CORE")
    print(line)
    print()


def load_operation_plan(path: Path) -> OperationPlan:
    return parse_operation_plan_json(path.read_text(encoding="utf-8"))


def parse_operation_plan_json(raw_json: str) -> OperationPlan:
    plan = OperationPlan.model_validate(json.loads(raw_json))
    validate_operation_plan(plan)
    return plan


def _run_plan_file(path: Path) -> int:
    _print_banner()
    try:
        plan = load_operation_plan(path)
        output_path = _generate_confirmed_model(plan)
    except (OSError, OperationValidationError, ValidationError, ValueError) as exc:
        print(exc)
        return 1
    if output_path is None:
        return 0
    _print_success(plan, output_path)
    _offer_save_project(plan, plan.project_name, f"Plan file: {path}")
    return 0


def _offer_save_project(spec: SupportedDesignSpec, default_name: str, source_prompt: str | None) -> None:
    try:
        if not _confirm("Save as editable SHAH project? [Y/n] "):
            return
        name = input(f"Project name [{default_name}]: ").strip() or default_name
        project, revision = create_project_from_model(
            name=name,
            model=spec,
            source_prompt=source_prompt,
        )
        print(f"Saved project {project.project_id} at revision {revision.revision_number}.")
    except (EOFError, StopIteration):
        return
    except Exception as exc:
        print(f"Project save skipped: {exc}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
