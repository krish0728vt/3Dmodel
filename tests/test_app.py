from __future__ import annotations

from pathlib import Path

import app
from ai.schemas import BoxSpec, HoleSpec, MountingPlateSpec, SupportedPartSpec


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


def test_natural_language_mode_displays_interpreted_spec(monkeypatch, capsys) -> None:
    inputs = iter(
        [
            "1",
            "Create a 100 x 60 x 5 mm mounting plate with four 5 mm holes 8 mm from each edge.",
            "y",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr(app, "parse_prompt", lambda _: sample_spec())
    monkeypatch.setattr(app, "generate_step", lambda spec, output_path: Path(output_path))

    assert app.main() == 0

    output = capsys.readouterr().out
    assert "INTERPRETED DESIGN" in output
    assert "Mounting Plate" in output
    assert "(-42, -22)" in output
    assert "Model generated successfully." in output


def test_manual_mode_still_builds_symmetric_four_hole_plate(monkeypatch) -> None:
    generated_specs: list[MountingPlateSpec] = []
    inputs = iter(["2", "1", "100", "60", "5", "4", "5", "8", "8", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    def fake_generate_step(spec: MountingPlateSpec, output_path: Path) -> Path:
        generated_specs.append(spec)
        return Path(output_path)

    monkeypatch.setattr(app, "generate_step", fake_generate_step)

    assert app.main() == 0

    spec = generated_specs[0]
    assert spec.width_mm == 100
    assert spec.height_mm == 60
    assert spec.thickness_mm == 5
    assert spec.corner_radius_mm == 4
    assert [(hole.x_mm, hole.y_mm) for hole in spec.holes] == [
        (-42, -22),
        (42, -22),
        (-42, 22),
        (42, 22),
    ]


def test_manual_mode_can_cancel_cleanly(monkeypatch, capsys) -> None:
    inputs = iter(["2", "1", "100", "60", "5", "4", "5", "8", "8", "n"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    assert app.main() == 0

    assert "Generation cancelled." in capsys.readouterr().out


def test_manual_mode_supports_box(monkeypatch) -> None:
    generated_specs: list[SupportedPartSpec] = []
    inputs = iter(["2", "2", "50", "30", "10", "2", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    def fake_generate_step(spec: SupportedPartSpec, output_path: Path) -> Path:
        generated_specs.append(spec)
        return Path(output_path)

    monkeypatch.setattr(app, "generate_step", fake_generate_step)

    assert app.main() == 0

    assert isinstance(generated_specs[0], BoxSpec)
    assert generated_specs[0].part_type == "box"
