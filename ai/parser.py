from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from ai.schemas import OperationPlan, PromptParseResponse, SupportedDesignSpec
from cad.operation_validator import OperationValidationError, validate_operation_plan
from cad.validator import GeometryValidationError, validate_part
from engineering.units import normalize_prompt_lengths_to_mm


DEFAULT_MODEL = "gpt-5-mini"


class PromptParserError(RuntimeError):
    """Base class for expected prompt parsing failures."""


class MissingApiKeyError(PromptParserError):
    """Raised when natural-language parsing is requested without an API key."""


class UnsupportedPartError(PromptParserError):
    """Raised when the prompt asks for an unsupported CAD part."""


class MissingInformationError(PromptParserError):
    """Raised when the prompt lacks required engineering dimensions."""


class MalformedAIResponseError(PromptParserError):
    """Raised when the AI response cannot be converted to the parser schema."""


class AIConnectionError(PromptParserError):
    """Raised when the OpenAI API request fails."""


SYSTEM_PROMPT = """
You are SHAH CAD's structured CAD interpreter.

Return only structured data matching the provided schema. Do not write CadQuery,
Python, STEP text, commentary, or markdown.

For common template parts, Milestone 4 still supports exactly these part_type values:
- mounting_plate
- box
- cylinder
- spacer
- l_bracket
- electronics_enclosure

For custom simple mechanical parts that do not fit a template, return an
OperationPlan using only the allowlisted operation_type values in the schema.
Never return Python, CadQuery code, expressions, formulas, or arbitrary commands.

Milestone 8 supports structured sketches and advanced feature operations. For
freeform profiles, create a create_sketch operation with typed sketch entities
only: line, polyline, rectangle, circle, arc, polygon, or slot. Use follow-up
feature operations such as extrude, cut_extrude, loft, sweep, shell,
through_hole, blind_hole, counterbore_hole, countersink_hole, boss, rib,
rectangular_hole_pattern, and circular_hole_pattern. Do not return raw CadQuery
selectors; use allowlisted face selectors such as top_face, bottom_face,
front_face, back_face, left_face, and right_face.

Examples:
- A pocket is a closed create_sketch plus cut_extrude.
- A hollow open-top box may use create_box plus shell with remove_face_selector
  top_face.
- A loft uses two or more closed create_sketch profiles with compatible planes.
- A swept tube uses a closed circular profile sketch and an open line/polyline
  path sketch.
- Countersunk holes use countersink_hole, not hand-modeled cones.

For supported prompts, return status "success" and a complete template spec or
operation plan in millimeters. Coordinate-based features are centered on the XY
origin.

If a prompt describes a rectangular mounting plate with four symmetric holes
specified by edge offsets, compute the four hole centers:
  x = width_mm / 2 - x_edge_offset_mm
  y = height_mm / 2 - y_edge_offset_mm
and return holes at (-x, -y), (x, -y), (-x, y), (x, y).

For electronics enclosures, use internal dimensions when the user references
PCB fit or internal size. Do not add mounting posts unless the prompt includes
post dimensions or clearly says four M3 posts near the corners; in that case use
3.2 mm holes, 6 mm outer diameter, and posts that fit inside the enclosure.

If the prompt asks for any unsupported part type, return status "unsupported".
If required dimensions are missing or ambiguous, return status
"missing_information" and list the missing fields in message.
Do not invent missing dimensions.
Units for this milestone are millimeters only.
""".strip()


def parse_prompt(
    prompt: str,
    *,
    client: Any | None = None,
    model: str | None = None,
) -> SupportedDesignSpec:
    """Parse natural language into a validated supported CAD part specification."""

    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise MissingInformationError("Describe a mounting plate before generating a model.")

    normalized_prompt = normalize_prompt_lengths_to_mm(cleaned_prompt)

    response = _request_structured_parse(normalized_prompt, client=client, model=model)
    spec = _spec_from_response(response)
    try:
        if isinstance(spec, OperationPlan):
            validate_operation_plan(spec)
        else:
            validate_part(spec)
    except (GeometryValidationError, OperationValidationError) as exc:
        raise MissingInformationError(str(exc)) from exc
    return spec


def _request_structured_parse(
    prompt: str,
    *,
    client: Any | None,
    model: str | None,
) -> PromptParseResponse:
    load_dotenv()
    selected_model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    if client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise MissingApiKeyError(
                "OPENAI_API_KEY is not set. Add it to your environment or use manual mode."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise MissingApiKeyError(
                "The openai package is not installed. Install requirements or use manual mode."
            ) from exc

        client = OpenAI()

    try:
        if hasattr(client.responses, "parse"):
            response = client.responses.parse(
                model=selected_model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                text_format=PromptParseResponse,
            )
        else:
            response = client.responses.create(
                model=selected_model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "cad_prompt_parse",
                        "schema": PromptParseResponse.model_json_schema(),
                        "strict": True,
                    }
                },
            )
    except Exception as exc:
        raise AIConnectionError(f"OpenAI API request failed: {exc}") from exc

    return _extract_parse_response(response)


def _spec_from_response(response: PromptParseResponse) -> SupportedDesignSpec:
    if response.status == "unsupported":
        raise UnsupportedPartError(
            response.message or "This version currently supports rectangular mounting plates only."
        )
    if response.status == "missing_information":
        raise MissingInformationError(response.message or "The prompt is missing required dimensions.")
    if response.spec is None:
        raise MalformedAIResponseError("The parser returned success without a CAD specification.")
    return response.spec


def _extract_parse_response(response: Any) -> PromptParseResponse:
    parsed = getattr(response, "output_parsed", None)
    if parsed is not None:
        return _coerce_parse_response(parsed)

    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            parsed = getattr(content_item, "parsed", None)
            if parsed is not None:
                return _coerce_parse_response(parsed)

    output_text = getattr(response, "output_text", None)
    if output_text:
        return _coerce_parse_response(output_text)

    raise MalformedAIResponseError("The parser response did not contain structured CAD data.")


def _coerce_parse_response(value: Any) -> PromptParseResponse:
    if isinstance(value, PromptParseResponse):
        return value

    try:
        if isinstance(value, str):
            return PromptParseResponse.model_validate_json(value)
        if isinstance(value, dict):
            return PromptParseResponse.model_validate(value)
        return PromptParseResponse.model_validate(json.loads(json.dumps(value)))
    except (TypeError, ValueError, ValidationError) as exc:
        raise MalformedAIResponseError(f"Malformed parser response: {exc}") from exc
