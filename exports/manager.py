from __future__ import annotations

import hashlib
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cadquery as cq

from ai.schemas import OperationPlan
from assemblies.manager import _component_workplane, assembly_engineering
from assemblies.store import AssemblyStore
from assemblies.transforms import apply_transform
from cad.generator import generate_workplane
from engineering.geometry import calculate_geometry_metrics
from exports.dxf import export_plan_sketch_dxf
from exports.manifest import write_manifest
from exports.models import (
    ComponentCoordinateMode,
    ExportBatchResult,
    ExportFormat,
    ExportRequest,
    ExportResult,
    ExportSourceType,
)
from exports.naming import controlled_output_dir, ensure_controlled_path, revision_filename
from exports.step import export_step_file, validate_step_round_trip
from exports.stl import export_stl_file, stl_metadata
from exports.store import ExportStore
from projects.serialization import model_from_json
from projects.store import ProjectStore


class ExportError(ValueError):
    """Raised when an export cannot be completed safely."""


def run_export(
    request: ExportRequest,
    *,
    project_store: ProjectStore | None = None,
    assembly_store: AssemblyStore | None = None,
    export_store: ExportStore | None = None,
) -> ExportBatchResult:
    project_store = project_store or ProjectStore()
    assembly_store = assembly_store or AssemblyStore()
    export_store = export_store or ExportStore()
    context = _resolve_context(request, project_store, assembly_store)
    output_dir = ensure_controlled_path(controlled_output_dir(request.source_id, context["revision"]))
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[ExportResult] = []
    warnings: list[str] = []
    formats = _normalized_formats(request)
    generated_at = _utc_now()

    for format_name in formats:
        if format_name in {ExportFormat.MANIFEST, ExportFormat.ZIP}:
            continue
        try:
            result = _export_single(format_name, request, context, output_dir, generated_at)
            _record(export_store, request, context, result)
            results.append(result)
        except ExportError:
            raise
        except Exception as exc:
            raise ExportError(f"{format_name.value.upper()} export failed: {exc}") from exc

    if request.options.include_manifest or ExportFormat.MANIFEST in formats or request.options.package or ExportFormat.ZIP in formats:
        manifest_result = _export_manifest(request, context, output_dir, generated_at, results)
        _record(export_store, request, context, manifest_result)
        results.append(manifest_result)

    if request.options.package or ExportFormat.ZIP in formats:
        zip_result = _export_zip(request, context, output_dir, generated_at, results)
        _record(export_store, request, context, zip_result)
        results.append(zip_result)

    return ExportBatchResult(
        request=request,
        source_name=context["source_name"],
        revision=context["revision"],
        revision_id=context.get("revision_id"),
        output_dir=str(output_dir),
        results=results,
        warnings=warnings,
    )


def checksum_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def result_from_path(format_name: ExportFormat, path: Path, *, created_at: str, warnings: list[str] | None = None, metadata: dict[str, Any] | None = None) -> ExportResult:
    _validate_file(path, format_name)
    return ExportResult(
        format=format_name,
        path=str(path),
        filename=path.name,
        size_bytes=path.stat().st_size,
        checksum_sha256=checksum_file(path),
        created_at=created_at,
        warnings=warnings or [],
        metadata=metadata or {},
    )


def _resolve_context(request: ExportRequest, project_store: ProjectStore, assembly_store: AssemblyStore) -> dict[str, Any]:
    if request.source_type == ExportSourceType.PROJECT_REVISION:
        project = project_store.get_project(request.source_id)
        if project is None:
            raise ExportError(f"Unknown project: {request.source_id}")
        revision_number = request.revision or project.current_revision
        revision = project_store.get_revision(request.source_id, revision_number)
        if revision is None:
            raise ExportError(f"Revision {revision_number} does not exist for project {request.source_id}.")
        model = model_from_json(revision.model_type, revision.structured_spec_json)
        part = generate_workplane(model)
        return {
            "source_name": project.name,
            "revision": revision.revision_number,
            "revision_id": revision.revision_id,
            "model": model,
            "part": part,
            "project": project,
            "material_id": project_store.get_material_assignment(project.project_id),
        }
    if request.source_type == ExportSourceType.ASSEMBLY_REVISION:
        assembly = assembly_store.get_assembly(request.source_id)
        if assembly is None:
            raise ExportError(f"Unknown assembly: {request.source_id}")
        revision_number = request.revision or assembly.current_revision
        revision = assembly_store.get_revision(request.source_id, revision_number)
        if revision is None:
            raise ExportError(f"Revision {revision_number} does not exist for assembly {request.source_id}.")
        part = _assembly_workplane(revision.components, project_store, request.options.component_mode)
        return {
            "source_name": assembly.name,
            "revision": revision.revision_number,
            "revision_id": revision.revision_id,
            "assembly": assembly,
            "assembly_revision": revision,
            "part": part,
        }
    if request.source_type == ExportSourceType.CAPABILITY_OUTPUT:
        source_path = _controlled_capability_output_path(request.source_id)
        part = cq.importers.importStep(str(source_path)) if source_path.suffix.lower() in {".step", ".stp"} else None
        return {
            "source_name": source_path.stem,
            "revision": request.revision or 1,
            "revision_id": None,
            "capability_path": source_path,
            "part": part,
        }
    raise ExportError(f"Unsupported export source type: {request.source_type.value}")


def _assembly_workplane(components: list[Any], project_store: ProjectStore, component_mode: ComponentCoordinateMode) -> cq.Workplane:
    shapes = []
    for component in components:
        if not component.visible:
            continue
        part = _component_workplane(component, project_store)
        if component_mode == ComponentCoordinateMode.ASSEMBLY_POSITIONED:
            part = apply_transform(part, component.transform)
        value = part.val()
        solids = value.Solids() if hasattr(value, "Solids") else []
        shapes.extend(solids or [value])
    if not shapes:
        raise ExportError("Assembly export requires at least one visible component.")
    return cq.Workplane("XY").newObject(shapes)


def _normalized_formats(request: ExportRequest) -> list[ExportFormat]:
    seen: set[ExportFormat] = set()
    formats: list[ExportFormat] = []
    for item in request.formats:
        if item not in seen:
            formats.append(item)
            seen.add(item)
    return formats


def _export_single(format_name: ExportFormat, request: ExportRequest, context: dict[str, Any], output_dir: Path, created_at: str) -> ExportResult:
    source_name = context["source_name"]
    revision = context["revision"]
    part = context["part"]
    if format_name == ExportFormat.STEP:
        path = ensure_controlled_path(output_dir / revision_filename(source_name, revision, ".step"))
        if request.source_type == ExportSourceType.CAPABILITY_OUTPUT and context["capability_path"].suffix.lower() in {".step", ".stp"}:
            shutil.copy2(context["capability_path"], path)
        else:
            if part is None:
                raise ExportError("STEP export requires loadable CAD geometry.")
            export_step_file(part, path)
        metadata: dict[str, Any] = {}
        warnings: list[str] = []
        if request.source_type == ExportSourceType.PROJECT_REVISION:
            metadata["round_trip"] = validate_step_round_trip(part, path)
        elif request.source_type == ExportSourceType.CAPABILITY_OUTPUT:
            warnings.append("Capability output export reused the local generated geometry file.")
        else:
            warnings.append("Assembly STEP preserves transformed solids where supported by the CAD kernel; feature history is not preserved.")
        return result_from_path(format_name, path, created_at=created_at, warnings=warnings, metadata=metadata)
    if format_name == ExportFormat.STL:
        path = ensure_controlled_path(output_dir / revision_filename(source_name, revision, ".stl"))
        if request.source_type == ExportSourceType.CAPABILITY_OUTPUT and context["capability_path"].suffix.lower() == ".stl":
            shutil.copy2(context["capability_path"], path)
        else:
            if part is None:
                raise ExportError("STL export requires loadable CAD geometry.")
            export_stl_file(part, path, request.options.stl_quality)
        bbox = _bbox_metadata(part) if part is not None else None
        metadata = stl_metadata(path, bbox)
        metadata["quality"] = request.options.stl_quality.value
        return result_from_path(format_name, path, created_at=created_at, metadata=metadata)
    if format_name == ExportFormat.DXF:
        if request.source_type != ExportSourceType.PROJECT_REVISION or not isinstance(context.get("model"), OperationPlan):
            raise ExportError("DXF export currently requires a project revision with a structured 2D sketch operation.")
        path = ensure_controlled_path(output_dir / revision_filename(source_name, revision, ".dxf"))
        export_plan_sketch_dxf(context["model"], path)
        return result_from_path(format_name, path, created_at=created_at, metadata={"units": "mm", "layers": ["OUTLINE", "HOLES", "CONSTRUCTION"]})
    if format_name in {ExportFormat.GLB, ExportFormat.OBJ}:
        raise ExportError(f"{format_name.value.upper()} export is deferred: no reliable local exporter is available in this environment.")
    raise ExportError(f"{format_name.value.upper()} is not a direct file export format.")


def _export_manifest(request: ExportRequest, context: dict[str, Any], output_dir: Path, created_at: str, results: list[ExportResult]) -> ExportResult:
    source_name = context["source_name"]
    revision = context["revision"]
    path = ensure_controlled_path(output_dir / revision_filename(source_name, revision, ".manifest.json"))
    engineering = _engineering_metadata(request, context)
    parameters = _parameter_metadata(context.get("model"))
    assembly = _assembly_metadata(context) if request.source_type == ExportSourceType.ASSEMBLY_REVISION else None
    write_manifest(
        path,
        source={
            "source_type": request.source_type.value,
            "source_id": request.source_id,
            "name": source_name,
            "revision": revision,
            "revision_id": context.get("revision_id"),
        },
        engineering=engineering,
        parameters=parameters,
        assembly=assembly,
        results=results,
        generated_at=created_at,
    )
    return result_from_path(ExportFormat.MANIFEST, path, created_at=created_at)


def _export_zip(request: ExportRequest, context: dict[str, Any], output_dir: Path, created_at: str, results: list[ExportResult]) -> ExportResult:
    path = ensure_controlled_path(output_dir / revision_filename(context["source_name"], context["revision"], ".zip"))
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for result in results:
            source = Path(result.path)
            if source.exists():
                archive.write(source, arcname=result.filename)
    return result_from_path(ExportFormat.ZIP, path, created_at=created_at, metadata={"entries": [result.filename for result in results]})


def _record(export_store: ExportStore, request: ExportRequest, context: dict[str, Any], result: ExportResult) -> None:
    record = export_store.add_record(
        source_type=request.source_type,
        source_id=request.source_id,
        revision=context["revision"],
        revision_id=context.get("revision_id"),
        format=result.format,
        path=result.path,
        filename=result.filename,
        size_bytes=result.size_bytes,
        checksum_sha256=result.checksum_sha256,
        metadata=result.metadata,
    )
    result.export_id = record.export_id


def _validate_file(path: Path, format_name: ExportFormat) -> None:
    if not path.exists():
        raise ExportError(f"Export did not create file: {path}")
    if path.stat().st_size <= 0:
        raise ExportError(f"Export created an empty file: {path}")
    expected = {
        ExportFormat.STEP: ".step",
        ExportFormat.STL: ".stl",
        ExportFormat.DXF: ".dxf",
        ExportFormat.MANIFEST: ".json",
        ExportFormat.ZIP: ".zip",
    }.get(format_name)
    if expected and path.suffix.lower() != expected:
        raise ExportError(f"Export extension mismatch for {format_name.value}: {path.name}")


def _bbox_metadata(part: cq.Workplane) -> dict[str, float]:
    box = part.val().BoundingBox()
    return {
        "xmin": float(box.xmin),
        "ymin": float(box.ymin),
        "zmin": float(box.zmin),
        "xmax": float(box.xmax),
        "ymax": float(box.ymax),
        "zmax": float(box.zmax),
        "xlen": float(box.xlen),
        "ylen": float(box.ylen),
        "zlen": float(box.zlen),
    }


def _engineering_metadata(request: ExportRequest, context: dict[str, Any]) -> dict[str, Any] | None:
    if request.source_type == ExportSourceType.ASSEMBLY_REVISION:
        try:
            report = assembly_engineering(assembly_id=request.source_id, revision_number=context["revision"])
            return report.model_dump(mode="json")
        except Exception:
            return None
    try:
        metrics = calculate_geometry_metrics(context["part"])
    except Exception:
        return None
    return metrics.model_dump(mode="json")


def _parameter_metadata(model: Any) -> list[dict[str, Any]]:
    if model is None:
        return []
    return [parameter.model_dump(mode="json") for parameter in getattr(model, "parameters", [])]


def _assembly_metadata(context: dict[str, Any]) -> dict[str, Any]:
    revision = context["assembly_revision"]
    return {
        "components": [
            {
                "component_id": component.component_id,
                "name": component.name,
                "source_type": component.source_type.value,
                "project_id": component.project_id,
                "project_revision": component.project_revision,
                "transform": component.transform.model_dump(mode="json"),
                "visible": component.visible,
                "grounded": component.grounded,
            }
            for component in revision.components
        ]
    }


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _controlled_capability_output_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise ExportError("Capability output export requires a relative controlled output path.")
    resolved = path.resolve()
    allowed = (Path("outputs") / "capabilities").resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise ExportError("Capability output export only accepts files under outputs/capabilities.") from exc
    if not path.exists() or not path.is_file():
        raise ExportError(f"Capability output file not found: {raw_path}")
    if path.suffix.lower() not in {".step", ".stp", ".stl"}:
        raise ExportError("Capability output export supports local STEP/STL files only.")
    return path
