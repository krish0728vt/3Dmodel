"""Authoring helper for the deterministic benchmark corpus.

Writes `benchmarks/cases/expanded.json`. Bounding boxes are computed from the
fixture dimensions rather than typed by hand, so an expectation cannot silently
disagree with the geometry it describes.

Run from the repository root:

    python benchmarks/build_cases.py

The existing `core.json` is left untouched; this file only adds cases.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


OUT_PATH = Path("benchmarks") / "cases" / "expanded.json"

# Cases marked smoke=True form the fast representative suite. The rest run only
# in the full suite, so `evaluate smoke` stays quick.
cases: list[dict[str, Any]] = []


def add(case: dict[str, Any]) -> None:
    cases.append(case)


def box_spec(w: float, d: float, h: float, radius: float = 0.0) -> dict[str, Any]:
    return {"part_type": "box", "width_mm": w, "depth_mm": d, "height_mm": h, "corner_radius_mm": radius}


def geo(x: float, y: float, z: float, solids: int = 1) -> dict[str, Any]:
    return {"bbox": {"x": x, "y": y, "z": z}, "solid_count": solids}


def plate(w: float, h: float, t: float, holes: list[dict[str, float]] | None = None, radius: float = 0.0) -> dict[str, Any]:
    return {
        "part_type": "mounting_plate",
        "width_mm": w,
        "height_mm": h,
        "thickness_mm": t,
        "corner_radius_mm": radius,
        "holes": holes or [],
    }


def template_case(
    case_id: str,
    name: str,
    category: str,
    prompt: str,
    spec: dict[str, Any],
    bbox: tuple[float, float, float],
    *,
    difficulty: str = "simple",
    part_type: str | None = None,
    smoke: bool = False,
    exports: list[str] | None = None,
) -> None:
    add(
        {
            "case_id": case_id,
            "name": name,
            "category": category,
            "difficulty": difficulty,
            "prompt": prompt,
            "mode": "template",
            "expected_part_type": part_type or spec["part_type"],
            "expected_export_formats": exports if exports is not None else ["step", "stl"],
            "fixture_spec": spec,
            "geometric_expectation": geo(*bbox),
            "smoke": smoke,
        }
    )


def plan_case(
    case_id: str,
    name: str,
    category: str,
    prompt: str,
    operations: list[dict[str, Any]],
    final: str,
    bbox: tuple[float, float, float],
    *,
    difficulty: str = "medium",
    operation_types: list[str] | None = None,
    smoke: bool = False,
    solids: int = 1,
    exports: list[str] | None = None,
) -> None:
    add(
        {
            "case_id": case_id,
            "name": name,
            "category": category,
            "difficulty": difficulty,
            "prompt": prompt,
            "mode": "operation_plan",
            "expected_operation_types": operation_types
            or sorted({op["operation_type"] for op in operations}),
            "expected_export_formats": exports if exports is not None else ["step", "stl"],
            "fixture_spec": {
                "schema_version": "1.2",
                "project_name": case_id,
                "operations": operations,
            "final_object_id": final,
            },
            "structural_expectation": {"min_operation_count": len(operations)},
            "geometric_expectation": geo(*bbox, solids=solids),
            "smoke": smoke,
        }
    )


def failure_case(
    case_id: str,
    name: str,
    prompt: str,
    *,
    mode: str = "template",
    spec: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
    assembly: dict[str, Any] | None = None,
    category: str = "invalid_inputs",
    failure_category: str = "cad_validation",
    difficulty: str = "medium",
    notes: str | None = None,
    smoke: bool = False,
) -> None:
    """A case that must fail cleanly rather than crash or silently succeed."""
    case: dict[str, Any] = {
        "case_id": case_id,
        "name": name,
        "category": category,
        "difficulty": difficulty,
        "prompt": prompt,
        "mode": mode,
        "expected_failure_category": failure_category,
        "smoke": smoke,
    }
    if spec is not None:
        case["fixture_spec"] = spec
    if plan is not None:
        case["fixture_spec"] = plan
    if assembly is not None:
        case["assembly_fixture"] = assembly
    if notes:
        case["notes"] = notes
    add(case)


# ---------------------------------------------------------------------------
# Basic primitives
# ---------------------------------------------------------------------------

template_case("prim_cube_020", "20 mm cube", "basic_primitives",
              "Create a 20 mm cube.", box_spec(20, 20, 20), (20, 20, 20), smoke=True)
template_case("prim_slab_120x80x6", "Thin slab", "basic_primitives",
              "Create a 120 x 80 x 6 mm slab.", box_spec(120, 80, 6), (120, 80, 6))
template_case("prim_tall_block", "Tall block", "basic_primitives",
              "Create a 25 x 25 x 90 mm block.", box_spec(25, 25, 90), (25, 25, 90))
template_case("prim_rounded_block", "Rounded block", "basic_primitives",
              "Create a 60 x 40 x 10 mm block with 5 mm rounded corners.",
              box_spec(60, 40, 10, radius=5), (60, 40, 10))
template_case("prim_cylinder_050x020", "Flat cylinder", "basic_primitives",
              "Create a 50 mm diameter, 20 mm tall cylinder.",
              {"part_type": "cylinder", "diameter_mm": 50, "height_mm": 20}, (50, 50, 20), smoke=True)
template_case("prim_cylinder_012x100", "Long rod", "basic_primitives",
              "Create a 12 mm diameter rod 100 mm long.",
              {"part_type": "cylinder", "diameter_mm": 12, "height_mm": 100}, (12, 12, 100))
template_case("prim_cylinder_bored", "Bored cylinder", "holes",
              "Create a 40 mm cylinder 15 mm tall with a 10 mm center hole.",
              {"part_type": "cylinder", "diameter_mm": 40, "height_mm": 15,
               "center_hole_diameter_mm": 10}, (40, 40, 15), smoke=True)

# ---------------------------------------------------------------------------
# Spacers and holes
# ---------------------------------------------------------------------------

template_case("spacer_030_008_012", "Spacer 30/8", "holes",
              "Create a 30 mm diameter spacer with an 8 mm center hole, 12 mm tall.",
              {"part_type": "spacer", "outer_diameter_mm": 30, "inner_diameter_mm": 8,
               "height_mm": 12}, (30, 30, 12), smoke=True)
template_case("spacer_thin_wall", "Thin-wall spacer", "holes",
              "Create a 16 mm spacer with a 12 mm bore, 6 mm tall.",
              {"part_type": "spacer", "outer_diameter_mm": 16, "inner_diameter_mm": 12,
               "height_mm": 6}, (16, 16, 6))
template_case("plate_single_center_hole", "Plate with center hole", "holes",
              "Create a 50 x 50 x 5 mm plate with a 10 mm center hole.",
              plate(50, 50, 5, [{"diameter_mm": 10, "x_mm": 0, "y_mm": 0}]), (50, 50, 5))
template_case("plate_two_holes", "Plate with two holes", "holes",
              "Create a 80 x 30 x 4 mm plate with two 6 mm holes 25 mm either side of center.",
              plate(80, 30, 4, [{"diameter_mm": 6, "x_mm": -25, "y_mm": 0},
                                {"diameter_mm": 6, "x_mm": 25, "y_mm": 0}]), (80, 30, 4))

# ---------------------------------------------------------------------------
# Mounting parts
# ---------------------------------------------------------------------------

template_case("mount_plate_100x60_four", "Four-hole mounting plate", "mounting_parts",
              "Create a 100 x 60 x 5 mm mounting plate with four 5 mm holes 8 mm from the corners.",
              plate(100, 60, 5, [{"diameter_mm": 5, "x_mm": x, "y_mm": y}
                                 for x in (-42, 42) for y in (-22, 22)]),
              (100, 60, 5), difficulty="medium", smoke=True)
template_case("mount_plate_rounded", "Rounded mounting plate", "mounting_parts",
              "Create a 70 x 70 x 6 mm plate with 8 mm rounded corners and a 12 mm center hole.",
              plate(70, 70, 6, [{"diameter_mm": 12, "x_mm": 0, "y_mm": 0}], radius=8),
              (70, 70, 6), difficulty="medium")
template_case("mount_plate_six_holes", "Six-hole rail plate", "mounting_parts",
              "Create a 150 x 40 x 5 mm rail plate with six 6 mm holes.",
              plate(150, 40, 5, [{"diameter_mm": 6, "x_mm": x, "y_mm": 0}
                                 for x in (-60, -36, -12, 12, 36, 60)]),
              (150, 40, 5), difficulty="medium")
template_case("mount_post_plate", "Plate with mounting posts", "mounting_parts",
              "Create a 60 x 60 x 4 mm plate with a 10 mm center hole.",
              plate(60, 60, 4, [{"diameter_mm": 10, "x_mm": 0, "y_mm": 0}]), (60, 60, 4))

# ---------------------------------------------------------------------------
# Brackets
# ---------------------------------------------------------------------------

template_case("bracket_l_60x60", "L bracket 60/60", "brackets",
              "Create an L bracket 60 mm tall, 60 mm wide, 40 mm deep, 5 mm thick.",
              {"part_type": "l_bracket", "width_mm": 60, "height_mm": 60,
               "leg_depth_mm": 40, "thickness_mm": 5, "corner_radius_mm": 0},
              (60, 40, 60), difficulty="medium", smoke=True)
template_case("bracket_l_tall", "Tall L bracket", "brackets",
              "Create an L bracket 100 mm tall, 40 mm wide, 30 mm deep, 4 mm thick.",
              {"part_type": "l_bracket", "width_mm": 40, "height_mm": 100,
               "leg_depth_mm": 30, "thickness_mm": 4, "corner_radius_mm": 0},
              (40, 30, 100), difficulty="medium")

# ---------------------------------------------------------------------------
# Enclosures
# ---------------------------------------------------------------------------

template_case("enclosure_pcb_70x45", "PCB enclosure", "enclosures",
              "Create an open-top enclosure for a 70 x 45 mm PCB.",
              {"part_type": "electronics_enclosure", "internal_width_mm": 70,
               "internal_depth_mm": 45, "internal_height_mm": 25, "wall_thickness_mm": 2.5,
               "bottom_thickness_mm": 2.5, "mounting_posts": []},
              (75, 50, 27.5), difficulty="medium", smoke=True)
template_case("enclosure_with_posts", "Enclosure with posts", "enclosures",
              "Create an enclosure for a 50 x 50 mm board with four mounting posts.",
              {"part_type": "electronics_enclosure", "internal_width_mm": 50,
               "internal_depth_mm": 50, "internal_height_mm": 20, "wall_thickness_mm": 2,
               "bottom_thickness_mm": 2, "mounting_posts": [
                   {"x_mm": x, "y_mm": y, "outer_diameter_mm": 6,
                    "hole_diameter_mm": 2.5, "height_mm": 6}
                   for x in (-20, 20) for y in (-20, 20)]},
              (54, 54, 22), difficulty="complex")
template_case("enclosure_tall", "Tall enclosure", "enclosures",
              "Create an enclosure for a 40 x 30 mm board, 60 mm deep internally.",
              {"part_type": "electronics_enclosure", "internal_width_mm": 40,
               "internal_depth_mm": 30, "internal_height_mm": 60, "wall_thickness_mm": 3,
               "bottom_thickness_mm": 3, "mounting_posts": []},
              (46, 36, 63), difficulty="medium")

# ---------------------------------------------------------------------------
# Booleans
# ---------------------------------------------------------------------------

plan_case("bool_union_two_boxes", "Union of two boxes", "boolean_operations",
          "Create two overlapping boxes and union them.",
          [{"id": "a", "operation_type": "create_box", "width_mm": 40, "depth_mm": 20,
            "height_mm": 10, "center": [0, 0, 5]},
           {"id": "b", "operation_type": "create_box", "width_mm": 20, "depth_mm": 40,
            "height_mm": 10, "center": [0, 0, 5]},
           {"id": "joined", "operation_type": "boolean_union", "target_id": "a", "tool_id": "b"}],
          "joined", (40, 40, 10), smoke=True)

plan_case("bool_cut_pocket", "Boolean cut pocket", "boolean_operations",
          "Create a block and cut a smaller block out of its middle.",
          [{"id": "block", "operation_type": "create_box", "width_mm": 60, "depth_mm": 40,
            "height_mm": 20, "center": [0, 0, 10]},
           {"id": "tool", "operation_type": "create_box", "width_mm": 30, "depth_mm": 20,
            "height_mm": 10, "center": [0, 0, 15]},
           {"id": "cut", "operation_type": "boolean_cut", "target_id": "block", "tool_id": "tool"}],
          "cut", (60, 40, 20))

plan_case("bool_boss_on_plate", "Boss on plate", "boolean_operations",
          "Create a plate with a 20 mm cylindrical boss on top.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 60, "depth_mm": 60,
            "height_mm": 6, "center": [0, 0, 3]},
           {"id": "boss", "operation_type": "create_cylinder", "diameter_mm": 20,
            "height_mm": 14, "center": [0, 0, 13], "axis": "z"},
           {"id": "joined", "operation_type": "boolean_union", "target_id": "base", "tool_id": "boss"}],
          "joined", (60, 60, 20))

# ---------------------------------------------------------------------------
# Hole features: through, blind, counterbore, countersink
# ---------------------------------------------------------------------------

plan_case("hole_through_plate", "Through hole", "holes",
          "Create a plate with a 8 mm through hole.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 50, "depth_mm": 50,
            "height_mm": 8, "center": [0, 0, 0]},
           {"id": "hole", "operation_type": "through_hole", "target_id": "base",
            "position": [0, 0], "hole_diameter_mm": 8, "face_selector": "top_face"}],
          "hole", (50, 50, 8), smoke=True)

plan_case("hole_blind_depth", "Blind hole", "holes",
          "Create a block with a 10 mm hole 6 mm deep.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 40, "depth_mm": 40,
            "height_mm": 20, "center": [0, 0, 0]},
           {"id": "hole", "operation_type": "blind_hole", "target_id": "base",
            "position": [0, 0], "hole_diameter_mm": 10, "depth_mm": 6,
            "face_selector": "top_face"}],
          "hole", (40, 40, 20))

plan_case("hole_counterbore", "Counterbore hole", "holes",
          "Create a plate with a counterbored 6 mm hole.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 50, "depth_mm": 50,
            "height_mm": 12, "center": [0, 0, 0]},
           {"id": "cb", "operation_type": "counterbore_hole", "target_id": "base",
            "position": [0, 0], "hole_diameter_mm": 6, "counterbore_diameter_mm": 12,
            "counterbore_depth_mm": 4, "face_selector": "top_face"}],
          "cb", (50, 50, 12), smoke=True)

plan_case("hole_countersink", "Countersink hole", "holes",
          "Create a plate with a countersunk 5 mm hole.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 50, "depth_mm": 50,
            "height_mm": 10, "center": [0, 0, 0]},
           {"id": "cs", "operation_type": "countersink_hole", "target_id": "base",
            "position": [0, 0], "hole_diameter_mm": 5, "countersink_diameter_mm": 10,
            "angle_deg": 90, "face_selector": "top_face"}],
          "cs", (50, 50, 10))

plan_case("hole_four_countersinks", "Four countersinks", "holes",
          "Create a plate with four countersunk mounting holes.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 90, "depth_mm": 55,
            "height_mm": 6, "center": [0, 0, 0]}]
          + [{"id": f"cs_{index}", "operation_type": "countersink_hole",
              "target_id": "base" if index == 0 else f"cs_{index - 1}",
              "position": list(position), "hole_diameter_mm": 4.5,
              "countersink_diameter_mm": 9, "angle_deg": 90, "face_selector": "top_face"}
             for index, position in enumerate([(-34, -17), (34, -17), (-34, 17), (34, 17)])],
          "cs_3", (90, 55, 6), difficulty="complex")

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

plan_case("pattern_rect_holes", "Rectangular hole pattern", "patterns",
          "Create a plate with a 3 by 2 rectangular hole pattern.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 100, "depth_mm": 60,
            "height_mm": 5, "center": [0, 0, 0]},
           {"id": "holes", "operation_type": "rectangular_hole_pattern", "target_id": "base",
            "hole_diameter_mm": 5, "count_x": 3, "count_y": 2,
            "spacing_x_mm": 30, "spacing_y_mm": 30, "center": [0, 0],
            "face_selector": "top_face"}],
          "holes", (100, 60, 5), smoke=True)

plan_case("pattern_circular_holes", "Circular hole pattern", "patterns",
          "Create a disc with six holes on a 40 mm bolt circle.",
          [{"id": "disc", "operation_type": "create_cylinder", "diameter_mm": 70,
            "height_mm": 6, "center": [0, 0, 0], "axis": "z"},
           {"id": "holes", "operation_type": "circular_hole_pattern", "target_id": "disc",
            "hole_diameter_mm": 5, "radius_mm": 20, "count": 6,
            "start_angle_deg": 0, "face_selector": "top_face"}],
          "holes", (70, 70, 6), difficulty="complex")

plan_case("pattern_linear_boss", "Linear pattern of bosses", "patterns",
          "Create a rail with four bosses spaced 20 mm apart.",
          [{"id": "rail", "operation_type": "create_box", "width_mm": 100, "depth_mm": 20,
            "height_mm": 6, "center": [0, 0, 3]},
           {"id": "boss", "operation_type": "create_cylinder", "diameter_mm": 10,
            "height_mm": 8, "center": [-30, 0, 10], "axis": "z"},
           {"id": "joined", "operation_type": "boolean_union", "target_id": "rail", "tool_id": "boss"},
           {"id": "pattern", "operation_type": "linear_pattern", "target_id": "joined",
            "count": 4, "spacing_mm": 20, "direction": "x"}],
          "pattern", (160, 20, 14), difficulty="complex")

# ---------------------------------------------------------------------------
# Fillets and chamfers
# ---------------------------------------------------------------------------

plan_case("fillet_block_edges", "Filleted block", "boolean_operations",
          "Create a block with 3 mm filleted edges.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 50, "depth_mm": 30,
            "height_mm": 12, "center": [0, 0, 0]},
           {"id": "rounded", "operation_type": "fillet", "target_id": "base", "radius_mm": 3}],
          "rounded", (50, 30, 12), smoke=True)

plan_case("chamfer_block_edges", "Chamfered block", "boolean_operations",
          "Create a block with a 2 mm chamfer.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 40, "depth_mm": 40,
            "height_mm": 10, "center": [0, 0, 0]},
           {"id": "chamfered", "operation_type": "chamfer", "target_id": "base", "distance_mm": 2}],
          "chamfered", (40, 40, 10))

# ---------------------------------------------------------------------------
# Sketches, extrude, pockets
# ---------------------------------------------------------------------------

plan_case("sketch_rect_extrude", "Extruded rectangle sketch", "sketches",
          "Sketch a 40 x 25 mm rectangle and extrude it 8 mm.",
          [{"id": "sk", "operation_type": "create_sketch_rectangle", "plane": "XY",
            "width_mm": 40, "height_mm": 25, "center": [0, 0, 0]},
           {"id": "solid", "operation_type": "extrude", "sketch_id": "sk", "distance_mm": 8}],
          "solid", (40, 25, 8), smoke=True)

plan_case("sketch_circle_extrude", "Extruded circle sketch", "sketches",
          "Sketch a 30 mm circle and extrude it 10 mm.",
          [{"id": "sk", "operation_type": "create_sketch_circle", "plane": "XY",
            "diameter_mm": 30, "center": [0, 0, 0]},
           {"id": "solid", "operation_type": "extrude", "sketch_id": "sk", "distance_mm": 10}],
          "solid", (30, 30, 10))

plan_case("sketch_pocket_through", "Sketch pocket through all", "sketches",
          "Create a plate and cut a rectangular pocket all the way through.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 60, "depth_mm": 40,
            "height_mm": 10, "center": [0, 0, 0]},
           {"id": "sk", "operation_type": "create_sketch_rectangle", "plane": "XY",
            "width_mm": 20, "height_mm": 12, "center": [0, 0, 0]},
           {"id": "pocket", "operation_type": "cut_extrude", "target_id": "base",
            "sketch_id": "sk", "extent_type": "through_all"}],
          "pocket", (60, 40, 10), difficulty="complex")

plan_case("sketch_pocket_blind", "Sketch pocket blind", "sketches",
          "Create a block and cut a 4 mm deep rectangular pocket.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 60, "depth_mm": 40,
            "height_mm": 15, "center": [0, 0, 0]},
           {"id": "sk", "operation_type": "create_sketch_rectangle", "plane": "XY",
            "width_mm": 24, "height_mm": 16, "center": [0, 0, 0]},
           {"id": "pocket", "operation_type": "cut_extrude", "target_id": "base",
            "sketch_id": "sk", "extent_type": "blind", "distance_mm": 4}],
          "pocket", (60, 40, 15), difficulty="complex")

# ---------------------------------------------------------------------------
# Shells
# ---------------------------------------------------------------------------

plan_case("shell_open_tray", "Shelled open tray", "shells",
          "Create a 60 x 40 x 20 mm tray with 2 mm walls, open on top.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 60, "depth_mm": 40,
            "height_mm": 20, "center": [0, 0, 0]},
           {"id": "shelled", "operation_type": "shell", "target_id": "base",
            "thickness_mm": 2, "remove_face_selector": "top_face"}],
          # A shell offsets outward. X and Y gain a wall on both sides
          # (60 + 2*2 = 64, 40 + 2*2 = 44), but the removed top face means Z
          # gains only the bottom wall: 20 + 2 = 22.
          "shelled", (64, 44, 22), smoke=True)

plan_case("shell_thick_wall", "Thick-wall shell", "shells",
          "Create a 50 mm cube shelled to 5 mm walls.",
          [{"id": "base", "operation_type": "create_box", "width_mm": 50, "depth_mm": 50,
            "height_mm": 50, "center": [0, 0, 0]},
           {"id": "shelled", "operation_type": "shell", "target_id": "base",
            "thickness_mm": 5, "remove_face_selector": "top_face"}],
          # 50 + 2*5 = 60 in X and Y; Z gains only the bottom wall: 50 + 5 = 55.
          "shelled", (60, 60, 55), difficulty="complex")

# ---------------------------------------------------------------------------
# Lofts and sweeps
# ---------------------------------------------------------------------------

plan_case("loft_square_to_circle", "Loft square to circle", "lofts",
          "Loft a 40 mm square up to a 20 mm circle over 30 mm.",
          [{"id": "bottom", "operation_type": "create_sketch",
            "sketch": {"id": "bottom", "plane": "XY", "origin": [0, 0, 0], "closed": True,
                       "entities": [{"entity_type": "rectangle", "width_mm": 40,
                                     "height_mm": 40}]}},
           {"id": "top", "operation_type": "create_sketch",
            "sketch": {"id": "top", "plane": "XY", "origin": [0, 0, 30], "closed": True,
                       "entities": [{"entity_type": "circle", "diameter_mm": 20}]}},
           {"id": "lofted", "operation_type": "loft", "sketch_ids": ["bottom", "top"],
            "ruled": False, "solid": True}],
          "lofted", (40, 40, 30), difficulty="advanced", smoke=True)

plan_case("loft_circle_to_circle", "Tapered loft", "lofts",
          "Loft a 50 mm circle to a 25 mm circle over 40 mm.",
          [{"id": "bottom", "operation_type": "create_sketch",
            "sketch": {"id": "bottom", "plane": "XY", "origin": [0, 0, 0], "closed": True,
                       "entities": [{"entity_type": "circle", "diameter_mm": 50}]}},
           {"id": "top", "operation_type": "create_sketch",
            "sketch": {"id": "top", "plane": "XY", "origin": [0, 0, 40], "closed": True,
                       "entities": [{"entity_type": "circle", "diameter_mm": 25}]}},
           {"id": "lofted", "operation_type": "loft", "sketch_ids": ["bottom", "top"],
            "ruled": True, "solid": True}],
          "lofted", (50, 50, 40), difficulty="advanced")

# ---------------------------------------------------------------------------
# Engineering analysis
# ---------------------------------------------------------------------------


def engineering_case(case_id: str, name: str, prompt: str, spec: dict[str, Any],
                     bbox: tuple[float, float, float], material: str,
                     mass_min: float, mass_max: float, *, smoke: bool = False,
                     difficulty: str = "simple") -> None:
    add({
        "case_id": case_id,
        "name": name,
        "category": "engineering_analysis",
        "difficulty": difficulty,
        "prompt": prompt,
        "mode": "engineering",
        "expected_part_type": spec["part_type"],
        "fixture_spec": spec,
        "engineering_expectation": {
            "material_id": material,
            "mass_min_g": mass_min,
            "mass_max_g": mass_max,
            "display_units": "mm",
        },
        "geometric_expectation": geo(*bbox),
        "smoke": smoke,
    })


# Aluminium 6061 is 2.70 g/cm3; steel 1018 is 7.87; ABS is 1.04.
engineering_case("eng_alu_plate_mass", "Aluminium plate mass",
                 "Analyze a 100 x 60 x 5 mm aluminium plate.",
                 plate(100, 60, 5), (100, 60, 5), "aluminum_6061", 75, 85, smoke=True)
engineering_case("eng_steel_block_mass", "Steel block mass",
                 "Analyze a 40 mm steel cube.", box_spec(40, 40, 40), (40, 40, 40),
                 "mild_steel", 480, 520, difficulty="medium")
engineering_case("eng_abs_cube_mass", "ABS cube mass",
                 "Analyze a 30 mm ABS cube.", box_spec(30, 30, 30), (30, 30, 30),
                 "abs", 26, 30)

# ---------------------------------------------------------------------------
# Assemblies
# ---------------------------------------------------------------------------


def component(name: str, spec: dict[str, Any], *, tx: float = 0, ty: float = 0, tz: float = 0,
              rx: float = 0, ry: float = 0, rz: float = 0, grounded: bool = False,
              visible: bool | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": name,
        "spec": spec,
        "transform": {
            "translation_x_mm": tx, "translation_y_mm": ty, "translation_z_mm": tz,
            "rotation_x_deg": rx, "rotation_y_deg": ry, "rotation_z_deg": rz,
        },
    }
    if grounded:
        entry["grounded"] = True
    if visible is not None:
        entry["visible"] = visible
    return entry


def assembly_case(case_id: str, name: str, prompt: str, components: list[dict[str, Any]],
                  *, interference: bool = False, difficulty: str = "medium",
                  smoke: bool = False) -> None:
    add({
        "case_id": case_id,
        "name": name,
        "category": "assemblies",
        "difficulty": difficulty,
        "prompt": prompt,
        "mode": "assembly",
        "assembly_fixture": {"expect_interference": interference, "components": components},
        "smoke": smoke,
    })


assembly_case("asm_two_plates_stacked", "Two stacked plates",
              "Create an assembly of two plates stacked 10 mm apart.",
              [component("Lower", box_spec(40, 40, 5), grounded=True),
               component("Upper", box_spec(40, 40, 5), tz=10)], smoke=True)

assembly_case("asm_four_component_frame", "Four-component frame",
              "Create a four-component frame assembly.",
              [component("Base", box_spec(80, 80, 5), grounded=True),
               component("PostA", box_spec(10, 10, 40), tx=-30, ty=-30, tz=5),
               component("PostB", box_spec(10, 10, 40), tx=30, ty=-30, tz=5),
               component("PostC", box_spec(10, 10, 40), tx=0, ty=30, tz=5)],
              # The posts share the base's top face, so bounding boxes touch.
              interference=True, difficulty="complex")

assembly_case("asm_rotated_bracket", "Rotated component",
              "Create an assembly with a bracket rotated 90 degrees about Z.",
              [component("Plate", box_spec(60, 60, 5), grounded=True),
               component("Bracket", box_spec(40, 10, 20), tz=5, rz=90)],
              # The bracket sits on the plate's top face.
              interference=True)

assembly_case("asm_rotated_x_axis", "Component rotated about X",
              "Create an assembly with a plate rotated 90 degrees about X.",
              [component("Base", box_spec(50, 50, 4), grounded=True),
               component("Wall", box_spec(50, 30, 4), tz=20, rx=90)])

assembly_case("asm_hidden_component", "Hidden component",
              "Create an assembly where one component is hidden.",
              [component("Visible", box_spec(30, 30, 5), grounded=True),
               component("Hidden", box_spec(20, 20, 5), tz=20, visible=False)])

assembly_case("asm_interference_overlap", "Overlapping components",
              "Create an assembly where two components occupy the same space.",
              [component("First", box_spec(30, 30, 10), grounded=True),
               component("Second", box_spec(30, 30, 10), tz=2)],
              interference=True, difficulty="complex", smoke=True)

assembly_case("asm_mass_aggregation", "Assembly mass aggregation",
              "Create a three-component assembly and total its mass.",
              [component("A", box_spec(20, 20, 20), grounded=True),
               component("B", box_spec(20, 20, 20), tx=40),
               component("C", box_spec(20, 20, 20), tx=80)],
              difficulty="complex")

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

template_case("export_step_only", "STEP export", "exports",
              "Export a plate to STEP.", plate(50, 40, 5), (50, 40, 5),
              exports=["step"], smoke=True)
template_case("export_stl_only", "STL export", "exports",
              "Export a plate to STL.", plate(50, 40, 5), (50, 40, 5), exports=["stl"])
template_case("export_step_and_stl", "STEP and STL export", "exports",
              "Export a bracket to STEP and STL.",
              {"part_type": "l_bracket", "width_mm": 50, "height_mm": 50,
               "leg_depth_mm": 30, "thickness_mm": 4, "corner_radius_mm": 0},
              (50, 30, 50), exports=["step", "stl"], difficulty="medium")
template_case("export_cylinder_step", "Cylinder STEP export", "exports",
              "Export a cylinder to STEP.",
              {"part_type": "cylinder", "diameter_mm": 35, "height_mm": 25},
              (35, 35, 25), exports=["step"])
plan_case("export_sketch_dxf", "Structured sketch export", "exports",
          "Create a sketched plate suitable for DXF export.",
          [{"id": "sk", "operation_type": "create_sketch_rectangle", "plane": "XY",
            "width_mm": 60, "height_mm": 40, "center": [0, 0, 0]},
           {"id": "solid", "operation_type": "extrude", "sketch_id": "sk", "distance_mm": 5}],
          "solid", (60, 40, 5), exports=["step", "stl"], difficulty="medium")

# ---------------------------------------------------------------------------
# Expected clean failures
# ---------------------------------------------------------------------------

failure_case("fail_negative_width", "Negative width",
             "Create a plate with a negative width.",
             spec=plate(-50, 40, 5), difficulty="simple", smoke=True,
             notes="Schema validation must reject a negative dimension.")

failure_case("fail_zero_thickness", "Zero thickness",
             "Create a plate with zero thickness.",
             spec=plate(50, 40, 0), difficulty="simple")

failure_case("fail_hole_larger_than_plate", "Hole larger than plate",
             "Create a 20 mm plate with a 40 mm hole.",
             spec=plate(20, 20, 3, [{"diameter_mm": 40, "x_mm": 0, "y_mm": 0}]))

failure_case("fail_spacer_bore_too_large", "Spacer bore exceeds outer diameter",
             "Create a 10 mm spacer with a 20 mm bore.",
             spec={"part_type": "spacer", "outer_diameter_mm": 10,
                   "inner_diameter_mm": 20, "height_mm": 5})

failure_case("fail_fillet_too_large", "Fillet larger than geometry",
             "Create a 10 mm thick plate with a 40 mm fillet.",
             mode="operation_plan",
             plan={"schema_version": "1.2", "project_name": "fail_fillet_too_large",
                   "operations": [
                       {"id": "base", "operation_type": "create_box", "width_mm": 40,
                        "depth_mm": 40, "height_mm": 10, "center": [0, 0, 0]},
                       {"id": "rounded", "operation_type": "fillet", "target_id": "base",
                        "radius_mm": 40}],
                   "final_object_id": "rounded"},
             failure_category="cad_generation", smoke=True,
             notes="Fillet radius exceeds the available edge geometry; the kernel rejects it.")

failure_case("fail_shell_thicker_than_body", "Shell thicker than body",
             "Shell a 10 mm box with 20 mm walls.",
             mode="operation_plan",
             plan={"schema_version": "1.2", "project_name": "fail_shell_thick",
                   "operations": [
                       {"id": "base", "operation_type": "create_box", "width_mm": 30,
                        "depth_mm": 30, "height_mm": 10, "center": [0, 0, 0]},
                       {"id": "shelled", "operation_type": "shell", "target_id": "base",
                        "thickness_mm": 20, "remove_face_selector": "top_face"}],
                   "final_object_id": "shelled"},
             failure_category="cad_generation",
             notes="Wall thickness exceeds the body; the kernel rejects it.")

failure_case("fail_invalid_reference", "Operation references unknown feature",
             "Cut a hole in a feature that does not exist.",
             mode="operation_plan",
             plan={"schema_version": "1.2", "project_name": "fail_bad_ref",
                   "operations": [
                       {"id": "base", "operation_type": "create_box", "width_mm": 30,
                        "depth_mm": 30, "height_mm": 10, "center": [0, 0, 0]},
                       {"id": "hole", "operation_type": "cut_hole", "target_id": "nope",
                        "diameter_mm": 5, "position": [0, 0], "direction": "z"}],
                   "final_object_id": "hole"},
             failure_category="cad_validation", smoke=True,
             notes="Reference to a non-existent operation id must be rejected.")

failure_case("fail_duplicate_operation_id", "Duplicate operation id",
             "Create two operations with the same identifier.",
             mode="operation_plan",
             plan={"schema_version": "1.2", "project_name": "fail_duplicate_id",
                   "operations": [
                       {"id": "base", "operation_type": "create_box", "width_mm": 30,
                        "depth_mm": 30, "height_mm": 10, "center": [0, 0, 0]},
                       {"id": "base", "operation_type": "create_box", "width_mm": 20,
                        "depth_mm": 20, "height_mm": 5, "center": [0, 0, 0]}],
                   "final_object_id": "base"},
             failure_category="cad_validation")

failure_case("fail_assembly_missing_source", "Assembly component without source",
             "Create an assembly whose component has no usable source.",
             mode="assembly",
             assembly={"expect_interference": False,
                       "components": [component("Ghost", {"part_type": "box",
                                                           "width_mm": -10,
                                                           "depth_mm": 10,
                                                           "height_mm": 10})]},
             category="invalid_inputs", failure_category="cad_generation",
             notes="An unusable component spec must fail the case, not abort the run.")

# ---------------------------------------------------------------------------
# Unsupported requests
# ---------------------------------------------------------------------------

for case_id, name, prompt in [
    ("unsupported_gearbox", "Unsupported gearbox", "Create a complete gearbox with helical gears."),
    ("unsupported_threaded_fastener", "Unsupported threaded fastener",
     "Create an M8 bolt with real ISO metric threads."),
    ("unsupported_sheet_metal_unfold", "Unsupported sheet metal unfold",
     "Create a sheet metal part and unfold the flat pattern."),
]:
    add({
        "case_id": case_id,
        "name": name,
        "category": "invalid_inputs",
        "difficulty": "advanced",
        "prompt": prompt,
        "mode": "template",
        "expected_status": "unsupported",
        "expected_failure_category": "expected_unsupported",
        "notes": "Outside the deterministic supported scope; must be refused cleanly.",
        "smoke": False,
    })

# ---------------------------------------------------------------------------
# Ambiguous requests
# ---------------------------------------------------------------------------

for case_id, name, prompt in [
    ("ambiguous_make_it_bigger", "Ambiguous resize", "Make it bigger."),
    ("ambiguous_move_the_hole", "Ambiguous hole move", "Move the hole over a bit."),
    ("ambiguous_thicker_wall", "Ambiguous wall", "Make the wall thicker."),
]:
    add({
        "case_id": case_id,
        "name": name,
        "category": "ambiguous_inputs",
        "difficulty": "medium",
        "prompt": prompt,
        "mode": "edit",
        "expected_status": "skipped",
        "expected_failure_category": "expected_ambiguity",
        "notes": "Under-specified; asking for clarification is the correct behavior.",
        "smoke": False,
    })

# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ids = [case["case_id"] for case in cases]
    duplicates = {case_id for case_id in ids if ids.count(case_id) > 1}
    if duplicates:
        raise SystemExit(f"duplicate case ids: {sorted(duplicates)}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps({"cases": cases}, indent=2) + "\n", encoding="utf-8"
    )
    smoke_count = sum(1 for case in cases if case.get("smoke"))
    print(f"wrote {len(cases)} cases to {OUT_PATH} ({smoke_count} marked smoke)")
