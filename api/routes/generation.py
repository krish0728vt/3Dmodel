from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ai.parser import PromptParserError, parse_prompt
from cad.generator import generate_step, generate_stl
from projects.manager import create_project_from_model
from projects.revisions import export_revision_stl
from projects.serialization import model_to_dict
from projects.store import ProjectStore

from api.dependencies import get_project_store
from api.schemas import GenerateRequest, GenerateResponse
from api.utils import parse_design_spec, project_summary, revision_summary


router = APIRouter(prefix="/api", tags=["generation"])


@router.post("/generate", response_model=GenerateResponse)
def generate_model(
    request: GenerateRequest,
    store: ProjectStore = Depends(get_project_store),
) -> GenerateResponse:
    if request.spec is None and not request.prompt:
        raise HTTPException(status_code=400, detail="Provide either prompt or spec.")

    try:
        model = parse_design_spec(request.spec) if request.spec is not None else parse_prompt(request.prompt or "")
        name = request.project_name or getattr(model, "project_name", None) or _default_project_name(model)
        if request.save_project:
            project, revision = create_project_from_model(
                name=name,
                model=model,
                source_prompt=request.prompt,
                store=store,
            )
            export_revision_stl(project.project_id, revision.revision_number, store=store)
            project = store.get_project(project.project_id) or project
            return GenerateResponse(
                project=project_summary(project),
                revision=revision_summary(revision),
                spec=model_to_dict(model),
                step_url=f"/api/projects/{project.project_id}/download/step",
                stl_url=f"/api/projects/{project.project_id}/download/stl",
                message="Project generated.",
            )

        step_path = generate_step(model, "outputs/model.step")
        stl_path = generate_stl(model, "outputs/model.stl")
        return GenerateResponse(
            project=None,
            revision=None,
            spec=model_to_dict(model),
            step_url=f"/{step_path.as_posix()}",
            stl_url=f"/{stl_path.as_posix()}",
            message="Model generated without project storage.",
        )
    except PromptParserError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _default_project_name(model: object) -> str:
    part_type = getattr(model, "part_type", None)
    if isinstance(part_type, str):
        return part_type.replace("_", " ").title()
    return "SHAH CAD Project"
