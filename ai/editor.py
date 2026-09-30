from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from ai.parser import DEFAULT_MODEL, AIConnectionError, MissingApiKeyError, MalformedAIResponseError
from projects.models import EditInstruction


EDIT_ADAPTER = TypeAdapter(EditInstruction)


class EditParseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    message: str
    edit: EditInstruction | None = None


SYSTEM_PROMPT = """
You are SHAH CAD's structured edit interpreter.

Return only a typed edit instruction matching the provided schema.
Never return Python, CadQuery code, JSON Patch, shell commands, or prose-only edits.

If a request is ambiguous, return status "ambiguous" and no edit.
If a request requires an unsupported capability, return status "unsupported" and no edit.
Use operation IDs when editing operation plans.
If the current spec has design parameters, prefer set_design_parameter for
governing/driving dimensions such as plate_width, hole_edge_offset, pcb_width,
clearance, or boss_diameter. Do not rewrite dependent coordinates manually when
a driving parameter controls them.
Milestone 8 operation plans may include structured sketches and advanced
features such as cut_extrude, loft, sweep, shell, countersink_hole,
counterbore_hole, boss, rib, and repeated hole patterns. Use set_parameter or
modify_operation edits to change fields such as thickness_mm, distance_mm,
angle_deg, countersink_diameter_mm, and nested sketch entity dimensions. Never
return raw CadQuery selectors or executable code.
""".strip()


class EditParserError(RuntimeError):
    """Base class for expected edit parsing failures."""


class AmbiguousEditError(EditParserError):
    """Raised when an edit request is ambiguous."""


class UnsupportedEditError(EditParserError):
    """Raised when an edit requires unsupported functionality."""


def parse_edit_request(
    instruction: str,
    current_spec: Any,
    *,
    relevant_lessons: list[str] | None = None,
    enabled_capabilities: list[str] | None = None,
    current_revision_number: int | None = None,
    client: Any | None = None,
    model: str | None = None,
) -> EditInstruction:
    """Parse a conversational edit into one safe structured edit instruction."""

    response = _request_edit_parse(
        instruction=instruction,
        current_spec=current_spec,
        relevant_lessons=relevant_lessons or [],
        enabled_capabilities=enabled_capabilities or [],
        current_revision_number=current_revision_number,
        client=client,
        model=model,
    )
    if response.status == "ambiguous":
        raise AmbiguousEditError(response.message)
    if response.status == "unsupported":
        raise UnsupportedEditError(response.message)
    if response.edit is None:
        raise MalformedAIResponseError("Edit parser returned success without an edit.")
    return response.edit


def _request_edit_parse(
    *,
    instruction: str,
    current_spec: Any,
    relevant_lessons: list[str],
    enabled_capabilities: list[str],
    current_revision_number: int | None,
    client: Any | None,
    model: str | None,
) -> EditParseResponse:
    load_dotenv()
    selected_model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    if client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise MissingApiKeyError(
                "OPENAI_API_KEY is not set. Use typed project edits or configure natural-language editing."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise MissingApiKeyError("The openai package is not installed.") from exc
        client = OpenAI()

    payload = {
        "instruction": instruction,
        "current_revision_number": current_revision_number,
        "current_spec": current_spec.model_dump(mode="json") if hasattr(current_spec, "model_dump") else current_spec,
        "relevant_lessons": relevant_lessons[:5],
        "enabled_capabilities": enabled_capabilities,
    }
    try:
        response = client.responses.parse(
            model=selected_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            text_format=EditParseResponse,
        )
    except Exception as exc:
        raise AIConnectionError(f"OpenAI edit parser request failed: {exc}") from exc
    return _extract_response(response)


def _extract_response(response: Any) -> EditParseResponse:
    parsed = getattr(response, "output_parsed", None)
    if parsed is not None:
        return _coerce(parsed)
    output_text = getattr(response, "output_text", None)
    if output_text:
        return _coerce(output_text)
    raise MalformedAIResponseError("Edit parser response did not contain structured data.")


def _coerce(value: Any) -> EditParseResponse:
    try:
        if isinstance(value, EditParseResponse):
            return value
        if isinstance(value, str):
            return EditParseResponse.model_validate_json(value)
        if isinstance(value, dict):
            return EditParseResponse.model_validate(value)
        return EditParseResponse.model_validate(json.loads(json.dumps(value)))
    except (TypeError, ValueError, ValidationError) as exc:
        raise MalformedAIResponseError(f"Malformed edit parser response: {exc}") from exc
