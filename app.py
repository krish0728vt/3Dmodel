from __future__ import annotations

import logging
from pathlib import Path

from ai.schemas import (
    BoxSpec,
    CylinderSpec,
    ElectronicsEnclosureSpec,
    HoleSpec,
    LBracketSpec,
    MountingPlateSpec,
    MountingPostSpec,
    SpacerSpec,
    SupportedPartSpec,
)
from ai.parser import (
    AIConnectionError,
    MalformedAIResponseError,
    MissingApiKeyError,
    MissingInformationError,
    UnsupportedPartError,
    parse_prompt,
)

logging.getLogger("fontTools").setLevel(logging.ERROR)

from cad.generator import DEFAULT_OUTPUT_PATH, generate_step
from cad.validator import GeometryValidationError


def _read_float(prompt: str) -> float:
    while True:
        raw_value = input(prompt).strip()
        try:
            return float(raw_value)
        except ValueError:
            print("Enter a numeric value in millimeters.")


def _read_choice(valid_choices: set[str]) -> str:
    while True:
        choice = input("> ").strip()
        if choice in valid_choices:
            return choice
        print(f"Choose one of: {', '.join(sorted(valid_choices))}.")


def _confirm(prompt: str) -> bool:
    response = input(prompt).strip().lower()
    return response in {"", "y", "yes"}


def create_symmetric_four_hole_plate(
    width_mm: float,
    height_mm: float,
    thickness_mm: float,
    corner_radius_mm: float,
    hole_diameter_mm: float,
    x_edge_offset_mm: float,
    y_edge_offset_mm: float,
) -> MountingPlateSpec:
    x = width_mm / 2 - x_edge_offset_mm
    y = height_mm / 2 - y_edge_offset_mm

    return MountingPlateSpec(
        width_mm=width_mm,
        height_mm=height_mm,
        thickness_mm=thickness_mm,
        corner_radius_mm=corner_radius_mm,
        holes=[
            HoleSpec(diameter_mm=hole_diameter_mm, x_mm=-x, y_mm=-y),
            HoleSpec(diameter_mm=hole_diameter_mm, x_mm=x, y_mm=-y),
            HoleSpec(diameter_mm=hole_diameter_mm, x_mm=-x, y_mm=y),
            HoleSpec(diameter_mm=hole_diameter_mm, x_mm=x, y_mm=y),
        ],
    )


def _print_banner() -> None:
    line = "=" * 50
    print(line)
    print("SHAH INDUSTRIES")
    print("AI CAD GENERATOR")
    print(line)
    print()


def _display_spec(spec: SupportedPartSpec) -> None:
    print("INTERPRETED DESIGN")
    print()
    print("Part:")
    print(_part_label(spec))
    print()
    for label, value in _spec_summary_lines(spec):
        print(label)
        print(value)
        print()


def _part_label(spec: SupportedPartSpec) -> str:
    labels = {
        "mounting_plate": "Mounting Plate",
        "box": "Box",
        "cylinder": "Cylinder",
        "spacer": "Spacer",
        "l_bracket": "L Bracket",
        "electronics_enclosure": "Electronics Enclosure",
    }
    return labels[spec.part_type]


def _spec_summary_lines(spec: SupportedPartSpec) -> list[tuple[str, str]]:
    if isinstance(spec, MountingPlateSpec):
        holes = "None"
        positions = "None"
        if spec.holes:
            holes = f"{len(spec.holes)} x diameter {spec.holes[0].diameter_mm:g} mm"
            positions = "\n".join(f"({hole.x_mm:g}, {hole.y_mm:g})" for hole in spec.holes)
        return [
            ("Width:", f"{spec.width_mm:g} mm"),
            ("Height:", f"{spec.height_mm:g} mm"),
            ("Thickness:", f"{spec.thickness_mm:g} mm"),
            ("Corner Radius:", f"{spec.corner_radius_mm:g} mm"),
            ("Holes:", holes),
            ("Positions:", positions),
        ]
    if isinstance(spec, BoxSpec):
        return [
            ("Width:", f"{spec.width_mm:g} mm"),
            ("Depth:", f"{spec.depth_mm:g} mm"),
            ("Height:", f"{spec.height_mm:g} mm"),
            ("Corner Radius:", f"{spec.corner_radius_mm:g} mm"),
        ]
    if isinstance(spec, CylinderSpec):
        center_hole = (
            f"{spec.center_hole_diameter_mm:g} mm"
            if spec.center_hole_diameter_mm is not None
            else "None"
        )
        return [
            ("Diameter:", f"{spec.diameter_mm:g} mm"),
            ("Height:", f"{spec.height_mm:g} mm"),
            ("Center Hole:", center_hole),
        ]
    if isinstance(spec, SpacerSpec):
        return [
            ("Outer Diameter:", f"{spec.outer_diameter_mm:g} mm"),
            ("Inner Diameter:", f"{spec.inner_diameter_mm:g} mm"),
            ("Height:", f"{spec.height_mm:g} mm"),
        ]
    if isinstance(spec, LBracketSpec):
        return [
            ("Width:", f"{spec.width_mm:g} mm"),
            ("Height:", f"{spec.height_mm:g} mm"),
            ("Leg Depth:", f"{spec.leg_depth_mm:g} mm"),
            ("Thickness:", f"{spec.thickness_mm:g} mm"),
            ("Corner Radius:", f"{spec.corner_radius_mm:g} mm"),
            ("Holes:", "Not supported for L brackets in this milestone"),
        ]
    if isinstance(spec, ElectronicsEnclosureSpec):
        posts = "None"
        if spec.mounting_posts:
            posts = "\n".join(
                (
                    f"({post.x_mm:g}, {post.y_mm:g}) "
                    f"OD {post.outer_diameter_mm:g} mm, hole {post.hole_diameter_mm:g} mm, "
                    f"height {post.height_mm:g} mm"
                )
                for post in spec.mounting_posts
            )
        return [
            ("Internal Width:", f"{spec.internal_width_mm:g} mm"),
            ("Internal Depth:", f"{spec.internal_depth_mm:g} mm"),
            ("Internal Height:", f"{spec.internal_height_mm:g} mm"),
            ("Wall Thickness:", f"{spec.wall_thickness_mm:g} mm"),
            ("Bottom Thickness:", f"{spec.bottom_thickness_mm:g} mm"),
            ("Corner Radius:", f"{spec.corner_radius_mm:g} mm"),
            ("Mounting Posts:", posts),
        ]
    raise TypeError(f"Unsupported part specification: {type(spec).__name__}")
    print()


def _generate_confirmed_model(spec: SupportedPartSpec) -> Path | None:
    _display_spec(spec)
    if not _confirm("Generate this model? [Y/n] "):
        print()
        print("Generation cancelled.")
        return None

    return generate_step(spec, DEFAULT_OUTPUT_PATH)


def _natural_language_mode() -> int:
    print("Describe the part you want to create:")
    print()
    prompt = input("> ")
    print()

    try:
        spec = parse_prompt(prompt)
        output_path = _generate_confirmed_model(spec)
    except (
        AIConnectionError,
        GeometryValidationError,
        MalformedAIResponseError,
        MissingApiKeyError,
        MissingInformationError,
        UnsupportedPartError,
    ) as exc:
        print(exc)
        return 1

    if output_path is None:
        return 0

    _print_success(spec, output_path)
    return 0


def _manual_mode() -> int:
    print("Choose a part type:")
    print("1. Mounting plate")
    print("2. Box")
    print("3. Cylinder")
    print("4. Spacer")
    print("5. L bracket")
    print("6. Electronics enclosure")
    print()
    part_choice = _read_choice({"1", "2", "3", "4", "5", "6"})
    print()

    try:
        spec = _read_manual_spec(part_choice)
        output_path = _generate_confirmed_model(spec)
    except GeometryValidationError as exc:
        print()
        print(exc)
        return 1

    if output_path is None:
        return 0

    _print_success(spec, output_path)
    return 0


def _read_manual_spec(part_choice: str) -> SupportedPartSpec:
    if part_choice == "1":
        return _read_mounting_plate_spec()
    if part_choice == "2":
        return BoxSpec(
            width_mm=_read_float("Box width in mm: "),
            depth_mm=_read_float("Box depth in mm: "),
            height_mm=_read_float("Box height in mm: "),
            corner_radius_mm=_read_float("Vertical corner radius in mm: "),
        )
    if part_choice == "3":
        diameter_mm = _read_float("Cylinder diameter in mm: ")
        height_mm = _read_float("Cylinder height in mm: ")
        center_hole = _read_float("Center hole diameter in mm (0 for none): ")
        return CylinderSpec(
            diameter_mm=diameter_mm,
            height_mm=height_mm,
            center_hole_diameter_mm=center_hole if center_hole > 0 else None,
        )
    if part_choice == "4":
        return SpacerSpec(
            outer_diameter_mm=_read_float("Spacer outer diameter in mm: "),
            inner_diameter_mm=_read_float("Spacer inner diameter in mm: "),
            height_mm=_read_float("Spacer height in mm: "),
        )
    if part_choice == "5":
        return LBracketSpec(
            width_mm=_read_float("L bracket width in mm: "),
            height_mm=_read_float("L bracket height in mm: "),
            leg_depth_mm=_read_float("L bracket leg depth in mm: "),
            thickness_mm=_read_float("L bracket thickness in mm: "),
            corner_radius_mm=_read_float("Corner radius in mm: "),
        )
    return _read_enclosure_spec()


def _read_mounting_plate_spec() -> MountingPlateSpec:
    width_mm = _read_float("Plate width in mm: ")
    height_mm = _read_float("Plate height in mm: ")
    thickness_mm = _read_float("Plate thickness in mm: ")
    corner_radius_mm = _read_float("Corner radius in mm: ")
    hole_diameter_mm = _read_float("Hole diameter in mm: ")
    x_edge_offset_mm = _read_float("Hole X offset from left/right edges in mm: ")
    y_edge_offset_mm = _read_float("Hole Y offset from top/bottom edges in mm: ")

    return create_symmetric_four_hole_plate(
        width_mm=width_mm,
        height_mm=height_mm,
        thickness_mm=thickness_mm,
        corner_radius_mm=corner_radius_mm,
        hole_diameter_mm=hole_diameter_mm,
        x_edge_offset_mm=x_edge_offset_mm,
        y_edge_offset_mm=y_edge_offset_mm,
    )


def _read_enclosure_spec() -> ElectronicsEnclosureSpec:
    internal_width_mm = _read_float("Internal width in mm: ")
    internal_depth_mm = _read_float("Internal depth in mm: ")
    internal_height_mm = _read_float("Internal height in mm: ")
    wall_thickness_mm = _read_float("Wall thickness in mm: ")
    bottom_thickness_mm = _read_float("Bottom thickness in mm: ")
    corner_radius_mm = _read_float("Outer corner radius in mm: ")
    posts: list[MountingPostSpec] = []
    post_count = int(_read_float("Mounting post count (0 for none): "))
    for index in range(post_count):
        print(f"Mounting post {index + 1}:")
        posts.append(
            MountingPostSpec(
                x_mm=_read_float("  X position in mm: "),
                y_mm=_read_float("  Y position in mm: "),
                outer_diameter_mm=_read_float("  Outer diameter in mm: "),
                hole_diameter_mm=_read_float("  Hole diameter in mm: "),
                height_mm=_read_float("  Height in mm: "),
            )
        )
    return ElectronicsEnclosureSpec(
        internal_width_mm=internal_width_mm,
        internal_depth_mm=internal_depth_mm,
        internal_height_mm=internal_height_mm,
        wall_thickness_mm=wall_thickness_mm,
        bottom_thickness_mm=bottom_thickness_mm,
        corner_radius_mm=corner_radius_mm,
        mounting_posts=posts,
    )


def _print_success(spec: SupportedPartSpec, output_path: Path) -> None:
    print()
    print("Model generated successfully.")
    print()
    print("Part:")
    print(_part_label(spec))
    print()
    for label, value in _spec_summary_lines(spec):
        print(label)
        print(value)
        print()
    print("Output:")
    print(output_path)


def main() -> int:
    _print_banner()
    print("1. Describe a part using natural language")
    print("2. Enter dimensions manually")
    print()
    choice = _read_choice({"1", "2"})
    print()

    if choice == "1":
        return _natural_language_mode()
    return _manual_mode()


if __name__ == "__main__":
    raise SystemExit(main())
