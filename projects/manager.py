from __future__ import annotations

from ai.schemas import OperationPlan, SupportedPartSpec
from cad.generator import generate_step
from projects.models import ProjectRecord
from projects.models import RevisionRecord
from projects.revisions import revision_output_path
from projects.serialization import model_to_json, model_type_for
from projects.store import ProjectStore
from parametrics.resolver import resolve_design_intent


def create_project_from_model(
    *,
    name: str,
    model: SupportedPartSpec | OperationPlan,
    source_prompt: str | None = None,
    user_instruction: str = "Initial model",
    store: ProjectStore | None = None,
) -> tuple[ProjectRecord, RevisionRecord]:
    store = store or ProjectStore()
    if getattr(model, "parameters", None) or getattr(model, "relationships", None):
        model = resolve_design_intent(model).resolved_model
    project = store.create_project(
        name=name,
        source_prompt=source_prompt,
        model_type=model_type_for(model),
    )
    output_path = revision_output_path(project.project_id, 1)
    generate_step(model, output_path)
    generate_step(model, "outputs/model.step")
    revision = store.add_revision(
        project_id=project.project_id,
        parent_revision_id=None,
        user_instruction=user_instruction,
        model_type=model_type_for(model),
        structured_spec_json=model_to_json(model),
        change_summary="Initial model",
        step_output_path=str(output_path),
    )
    return project, revision
