"""Standard error shape for the user-facing workflows.

Expected failures are returned as:

    {"error": {"code": "...", "message": "...", "details": {...}}}

`code` is the internal failure category, which the frontend maps to a
plain-language title; `message` is already written for a person. `details`
carries structured context such as the operation id, and never a stack trace or
any environment value.

Applied to the major workflows (generation, editing, exports) rather than
rewritten across every endpoint, so the change stays low risk.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Envelope returned for an expected, explainable failure."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorBody


def error_payload(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the response body. Keeps the envelope in one place."""
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return {"error": body}


def api_error(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> HTTPException:
    """An HTTPException whose detail is the standard envelope.

    FastAPI serializes `detail` as-is, so the client receives
    `{"detail": {"error": {...}}}`. Callers that need the bare envelope at the
    top level should return `ErrorResponse` with an explicit status instead.
    """
    return HTTPException(status_code=status_code, detail=error_payload(code, message, details))


# Codes used by the workflows that return this shape. Kept as constants so the
# frontend mapping and the backend cannot drift on spelling.
CODE_VALIDATION = "schema_error"
CODE_UNSUPPORTED_PART = "unsupported_part"
CODE_MISSING_PARAMETER = "missing_parameter"
CODE_AMBIGUOUS = "ambiguous_request"
CODE_CAD_GENERATION = "invalid_geometry"
CODE_EXPORT = "export_failure"
CODE_NOT_FOUND = "not_found"
CODE_AI_NOT_CONFIGURED = "ai_not_configured"
