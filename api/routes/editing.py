from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import TypeAdapter, ValidationError

from ai.editor import EditParserError, parse_edit_request
from capabilities.registry import CapabilityRegistry
from learning.retrieval import get_relevant_lessons
from learning.store import LearningStore
from projects.editor import EditApplicationError, apply_edit_to_project
from projects.models import EditInstruction
from projects.revisions import export_revision_stl
from projects.serialization import model_from_json
from projects.store import ProjectStore

from api.dependencies import get_capability_registry, get_learning_store, get_project_store
from api.schemas import EditProjectRequest, EditProjectResponse
from api.utils import revision_summary


router = APIRouter(prefix="/api/projects", tags=["editing"])
EDIT_ADAPTER = TypeAdapter(EditInstruction)


@router.post("/{project_id}/edit", response_model=EditProjectResponse)
def edit_project(
    project_id: str,
    request: EditProjectRequest,
    store: ProjectStore = Depends(get_project_store),
    learning_store: LearningStore = Depends(get_learning_store),
    registry: CapabilityRegistry = Depends(get_capability_registry),
) -> EditProjectResponse:
    current_revision = store.current_revision(project_id)
    if current_revision is None:
        raise HTTPException(status_code=404, detail="Project or revision not found.")

    try:
        if request.edit is not None:
            edit = EDIT_ADAPTER.validate_python(request.edit)
            user_instruction = request.instruction or "Structured edit"
        elif request.instruction:
            current_model = model_from_json(current_revision.model_type, current_revision.structured_spec_json)
            lessons = get_relevant_lessons(store=learning_store, prompt=request.instruction, limit=5)
            capabilities = [cap.capability_id for cap in registry.enabled_for_generation()]
            edit = parse_edit_request(
                request.instruction,
                current_model,
                relevant_lessons=[lesson.description for lesson in lessons],
                enabled_capabilities=capabilities,
                current_revision_number=current_revision.revision_number,
            )
            user_instruction = request.instruction
        else:
            raise HTTPException(status_code=400, detail="Provide instruction or structured edit.")

        revision, summary = apply_edit_to_project(
            project_id=project_id,
            edit=edit,
            user_instruction=user_instruction,
            store=store,
            learning_store=learning_store,
        )
        export_revision_stl(project_id, revision.revision_number, store=store)
        return EditProjectResponse(
            project_id=project_id,
            revision=revision_summary(revision),
            change_summary=summary,
            stl_url=f"/api/projects/{project_id}/download/stl",
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except (EditApplicationError, EditParserError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
