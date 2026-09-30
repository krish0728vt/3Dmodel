from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError

from ai.schemas import OperationPlan, SupportedDesignSpec
from parametrics.migration import normalize_operation_schema_version
from projects.models import ProjectRecord, RevisionRecord
from projects.serialization import model_from_json, model_to_dict

from .schemas import ProjectDetail, ProjectSummary, RevisionSummary


DESIGN_ADAPTER = TypeAdapter(SupportedDesignSpec)


def parse_design_spec(raw: dict[str, Any]) -> SupportedDesignSpec:
    try:
        if "operations" in raw:
            return normalize_operation_schema_version(OperationPlan.model_validate(raw))
        return DESIGN_ADAPTER.validate_python(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


def project_summary(project: ProjectRecord, *, material: str | None = None) -> ProjectSummary:
    return ProjectSummary(
        project_id=project.project_id,
        name=project.name,
        created_at=project.created_at,
        updated_at=project.updated_at,
        current_revision=project.current_revision,
        source_prompt=project.source_prompt,
        model_type=project.model_type,
        status=project.status.value,
        archived_at=project.archived_at,
        last_opened_at=project.last_opened_at,
        thumbnail_url=f"/api/projects/{project.project_id}/thumbnail",
        material=material,
    )


def revision_summary(revision: RevisionRecord) -> RevisionSummary:
    return RevisionSummary(
        revision_id=revision.revision_id,
        project_id=revision.project_id,
        revision_number=revision.revision_number,
        parent_revision_id=revision.parent_revision_id,
        timestamp=revision.timestamp,
        user_instruction=revision.user_instruction,
        model_type=revision.model_type,
        change_summary=revision.change_summary,
        step_output_path=revision.step_output_path,
        generation_status=revision.generation_status.value,
        validation_status=revision.validation_status.value,
    )


def project_detail(project: ProjectRecord, revision: RevisionRecord | None) -> ProjectDetail:
    current_model = None
    if revision is not None:
        current_model = model_to_dict(model_from_json(revision.model_type, revision.structured_spec_json))
    return ProjectDetail(
        **project_summary(project).model_dump(),
        current_revision_record=revision_summary(revision) if revision else None,
        current_model=current_model,
    )
