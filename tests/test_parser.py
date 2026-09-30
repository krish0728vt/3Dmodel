from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai.parser import MissingInformationError, UnsupportedPartError, parse_prompt
from ai.schemas import (
    BoxSpec,
    CreateBoxOperation,
    CreateCylinderOperation,
    BooleanUnionOperation,
    CylinderSpec,
    HoleSpec,
    MountingPlateSpec,
    OperationPlan,
    PromptParseResponse,
)
from cad.generator import build_mounting_plate


class MockResponses:
    def __init__(self, parse_response: PromptParseResponse) -> None:
        self.parse_response = parse_response
        self.last_input: object | None = None

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.last_input = kwargs.get("input")
        return SimpleNamespace(output_parsed=self.parse_response)


class MockClient:
    def __init__(self, parse_response: PromptParseResponse) -> None:
        self.responses = MockResponses(parse_response)


def sample_spec() -> MountingPlateSpec:
    return MountingPlateSpec(
        width_mm=100,
        height_mm=60,
        thickness_mm=5,
        corner_radius_mm=4,
        holes=[
            HoleSpec(diameter_mm=5, x_mm=-42, y_mm=-22),
            HoleSpec(diameter_mm=5, x_mm=42, y_mm=-22),
            HoleSpec(diameter_mm=5, x_mm=-42, y_mm=22),
            HoleSpec(diameter_mm=5, x_mm=42, y_mm=22),
        ],
    )


def test_successful_prompt_parsing_returns_mounting_plate_spec() -> None:
    client = MockClient(
        PromptParseResponse(status="success", message="Mounting plate parsed.", spec=sample_spec())
    )

    spec = parse_prompt(
        "Create a 100 x 60 x 5 mm mounting plate with four 5 mm holes 8 mm from each edge.",
        client=client,
    )

    assert spec.width_mm == 100
    assert spec.height_mm == 60
    assert spec.thickness_mm == 5
    assert spec.corner_radius_mm == 4
    assert len(spec.holes) == 4


def test_unsupported_part_type_is_reported() -> None:
    client = MockClient(
        PromptParseResponse(
            status="unsupported",
            message="This version currently supports rectangular mounting plates only.",
            spec=None,
        )
    )

    with pytest.raises(UnsupportedPartError, match="mounting plates only"):
        parse_prompt("Create a gear.", client=client)


def test_missing_required_dimensions_are_reported() -> None:
    client = MockClient(
        PromptParseResponse(
            status="missing_information",
            message="Missing width_mm, height_mm, and thickness_mm.",
            spec=None,
        )
    )

    with pytest.raises(MissingInformationError, match="Missing width_mm"):
        parse_prompt("Make me a mounting plate.", client=client)


def test_inches_are_normalized_before_structured_parser_request() -> None:
    client = MockClient(
        PromptParseResponse(status="success", message="Should not be used.", spec=sample_spec())
    )

    parse_prompt("Make a 4 inch by 2 inch plate.", client=client)

    assert client.responses.last_input is not None
    user_message = client.responses.last_input[1]["content"]
    assert "101.6 mm" in user_message
    assert "50.8 mm" in user_message


def test_invalid_interpreted_geometry_is_reported() -> None:
    invalid_spec = MountingPlateSpec(
        width_mm=100,
        height_mm=60,
        thickness_mm=5,
        corner_radius_mm=4,
        holes=[HoleSpec(diameter_mm=10, x_mm=49, y_mm=0)],
    )
    client = MockClient(
        PromptParseResponse(status="success", message="Mounting plate parsed.", spec=invalid_spec)
    )

    with pytest.raises(MissingInformationError, match="left/right"):
        parse_prompt("Create a mounting plate with a hole too close to the edge.", client=client)


def test_parsed_spec_can_feed_existing_generator() -> None:
    client = MockClient(
        PromptParseResponse(status="success", message="Mounting plate parsed.", spec=sample_spec())
    )

    spec = parse_prompt("Create a 100 by 60 by 5 mm mounting plate.", client=client)
    part = build_mounting_plate(spec)

    assert part.val().Volume() > 0


@pytest.mark.parametrize(
    ("prompt", "spec", "expected_part_type"),
    [
        (
            "Make a box 50 x 30 x 10 mm.",
            BoxSpec(width_mm=50, depth_mm=30, height_mm=10, corner_radius_mm=0),
            "box",
        ),
        (
            "Create a cylinder 25mm diameter and 100mm long.",
            CylinderSpec(diameter_mm=25, height_mm=100),
            "cylinder",
        ),
    ],
)
def test_parser_dispatches_supported_part_types(
    prompt: str,
    spec,
    expected_part_type: str,
) -> None:
    client = MockClient(PromptParseResponse(status="success", message="Parsed.", spec=spec))

    parsed = parse_prompt(prompt, client=client)

    assert parsed.part_type == expected_part_type


def test_parser_dispatches_operation_plan() -> None:
    plan = OperationPlan(
        project_name="base_with_boss",
        operations=[
            CreateBoxOperation(id="base", width_mm=80, depth_mm=50, height_mm=5),
            CreateCylinderOperation(id="boss", diameter_mm=20, height_mm=15, center=(0, 0, 10)),
            BooleanUnionOperation(id="combined", target_id="base", tool_id="boss"),
        ],
        final_object_id="combined",
    )
    client = MockClient(PromptParseResponse(status="success", message="Parsed.", spec=plan))

    parsed = parse_prompt("Create a base plate with a cylindrical boss.", client=client)

    assert isinstance(parsed, OperationPlan)
    assert parsed.final_object_id == "combined"
