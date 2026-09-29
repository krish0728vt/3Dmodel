from __future__ import annotations

import pytest

from ai.schemas import HoleSpec, MountingPlateSpec
from cad.validator import GeometryValidationError, validate_mounting_plate


def valid_spec(**overrides: object) -> MountingPlateSpec:
    data = {
        "width_mm": 100,
        "height_mm": 60,
        "thickness_mm": 5,
        "corner_radius_mm": 4,
        "holes": [
            HoleSpec(diameter_mm=5, x_mm=-42, y_mm=-22),
            HoleSpec(diameter_mm=5, x_mm=42, y_mm=-22),
            HoleSpec(diameter_mm=5, x_mm=-42, y_mm=22),
            HoleSpec(diameter_mm=5, x_mm=42, y_mm=22),
        ],
    }
    data.update(overrides)
    return MountingPlateSpec(**data)


def assert_invalid(spec: MountingPlateSpec, expected_text: str) -> None:
    with pytest.raises(GeometryValidationError, match=expected_text):
        validate_mounting_plate(spec)


def test_negative_plate_dimensions_are_rejected() -> None:
    assert_invalid(valid_spec(width_mm=-100), "width_mm")


def test_zero_thickness_is_rejected() -> None:
    assert_invalid(valid_spec(thickness_mm=0), "thickness_mm")


def test_invalid_corner_radii_are_rejected() -> None:
    assert_invalid(valid_spec(corner_radius_mm=-1), "corner_radius_mm")
    assert_invalid(valid_spec(corner_radius_mm=40), "cannot exceed")


def test_negative_or_zero_hole_diameters_are_rejected() -> None:
    assert_invalid(valid_spec(holes=[HoleSpec(diameter_mm=0, x_mm=0, y_mm=0)]), "diameter_mm")
    assert_invalid(valid_spec(holes=[HoleSpec(diameter_mm=-5, x_mm=0, y_mm=0)]), "diameter_mm")


def test_holes_outside_the_plate_are_rejected() -> None:
    assert_invalid(valid_spec(holes=[HoleSpec(diameter_mm=5, x_mm=60, y_mm=0)]), "left/right")
    assert_invalid(valid_spec(holes=[HoleSpec(diameter_mm=5, x_mm=0, y_mm=40)]), "top/bottom")


def test_holes_too_close_to_plate_edge_are_rejected() -> None:
    assert_invalid(valid_spec(holes=[HoleSpec(diameter_mm=10, x_mm=46, y_mm=0)]), "left/right")
    assert_invalid(valid_spec(holes=[HoleSpec(diameter_mm=10, x_mm=0, y_mm=26)]), "top/bottom")


def test_valid_mounting_plate_passes_validation() -> None:
    validate_mounting_plate(valid_spec())
