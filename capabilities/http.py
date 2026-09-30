from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from capabilities.models import CapabilityErrorCategory, CapabilityRecord
from capabilities.invocation import CapabilityInvocationError
from config import CONFIG


def invoke_http_capability(record: CapabilityRecord, arguments: dict[str, Any]) -> dict[str, Any]:
    if not record.endpoint:
        raise CapabilityInvocationError(CapabilityErrorCategory.CONNECTION_FAILURE, "HTTP capability has no endpoint.")
    if not record.endpoint.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        raise CapabilityInvocationError(CapabilityErrorCategory.PERMISSION_FAILURE, "HTTP capability endpoint scheme is not allowed.")
    body = json.dumps(arguments).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if record.token_env:
        token = os.getenv(record.token_env)
        if token:
            headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(record.endpoint, data=body, headers=headers, method=record.http_method)
    try:
        with urllib.request.urlopen(request, timeout=CONFIG.capability_call_timeout_seconds) as response:
            content_type = response.headers.get("content-type", "")
            payload = response.read(1_000_000)
    except TimeoutError as exc:
        raise CapabilityInvocationError(CapabilityErrorCategory.TIMEOUT, "HTTP capability timed out.") from exc
    except urllib.error.URLError as exc:
        raise CapabilityInvocationError(CapabilityErrorCategory.CONNECTION_FAILURE, str(exc)) from exc
    if "application/json" not in content_type:
        raise CapabilityInvocationError(CapabilityErrorCategory.OUTPUT_VALIDATION_FAILURE, "HTTP capability returned non-JSON content.")
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except ValueError as exc:
        raise CapabilityInvocationError(CapabilityErrorCategory.OUTPUT_VALIDATION_FAILURE, "HTTP capability returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise CapabilityInvocationError(CapabilityErrorCategory.OUTPUT_VALIDATION_FAILURE, "HTTP capability result must be an object.")
    return parsed
