from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai.editor import EditParseResponse, UnsupportedEditError, parse_edit_request
from ai.schemas import BoxSpec
from projects.models import SetParameterEdit


class MockResponses:
    def __init__(self, response: EditParseResponse) -> None:
        self.response = response

    def parse(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(output_parsed=self.response)


class MockClient:
    def __init__(self, response: EditParseResponse) -> None:
        self.responses = MockResponses(response)


def test_edit_parser_returns_structured_edit() -> None:
    edit = SetParameterEdit(path="width_mm", value=20)
    client = MockClient(EditParseResponse(status="success", message="ok", edit=edit))

    parsed = parse_edit_request("make it wider", BoxSpec(width_mm=10, depth_mm=20, height_mm=5), client=client)

    assert isinstance(parsed, SetParameterEdit)
    assert parsed.path == "width_mm"


def test_unsupported_capability_request_is_rejected_cleanly() -> None:
    client = MockClient(
        EditParseResponse(
            status="unsupported",
            message="This model currently has no enabled threaded-hole capability.",
            edit=None,
        )
    )

    with pytest.raises(UnsupportedEditError, match="threaded-hole capability"):
        parse_edit_request("add an M6 threaded hole", BoxSpec(width_mm=10, depth_mm=20, height_mm=5), client=client)
