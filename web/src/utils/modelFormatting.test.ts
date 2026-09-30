import { describe, expect, it } from "vitest";

import { operationDetails, operationDisplayName, operationKind, templateDetails } from "./modelFormatting";

describe("operationDisplayName", () => {
  it("prefers an explicit label", () => {
    expect(operationDisplayName({ label: "Main Pocket", operation_type: "cut_extrude" })).toBe("Main Pocket");
  });

  it("falls back to the friendly name when the label is blank", () => {
    expect(operationDisplayName({ label: "   ", operation_type: "cut_extrude" })).toBe("Pocket");
  });

  it("humanises unknown operation types", () => {
    expect(operationDisplayName({ operation_type: "some_new_feature" })).toBe("some new feature");
  });

  it("handles a missing operation type", () => {
    expect(operationDisplayName({})).toBe("operation");
  });
});

describe("operationKind", () => {
  it("ignores the label and reports the underlying kind", () => {
    expect(operationKind({ label: "Main Pocket", operation_type: "cut_extrude" })).toBe("Pocket");
  });

  it("maps known operation types", () => {
    expect(operationKind({ operation_type: "counterbore_hole" })).toBe("Counterbore");
  });
});

describe("operationDetails", () => {
  it("describes a through-all pocket without a distance", () => {
    expect(
      operationDetails({
        operation_type: "cut_extrude",
        target_id: "body1",
        sketch_id: "sk1",
        extent_type: "through_all",
        distance_mm: 10
      })
    ).toEqual([
      ["Target", "body1"],
      ["Sketch", "sk1"],
      ["Distance", "through all"]
    ]);
  });

  it("describes a blind pocket with its distance in millimetres", () => {
    expect(
      operationDetails({
        operation_type: "cut_extrude",
        target_id: "body1",
        sketch_id: "sk1",
        extent_type: "blind",
        distance_mm: 4.5
      })
    ).toEqual([
      ["Target", "body1"],
      ["Sketch", "sk1"],
      ["Distance", "4.5 mm"]
    ]);
  });

  it("joins loft profile lists", () => {
    expect(operationDetails({ operation_type: "loft", sketch_ids: ["a", "b"], ruled: true })).toEqual([
      ["Profiles", "a, b"],
      ["Ruled", "true"]
    ]);
  });

  it("defaults a shell removed face and a boss face", () => {
    expect(operationDetails({ operation_type: "shell", target_id: "b1", thickness_mm: 2 })).toEqual([
      ["Target", "b1"],
      ["Thickness", "2 mm"],
      ["Removed Face", "none"]
    ]);
    expect(operationDetails({ operation_type: "boss", diameter_mm: 8, height_mm: 4 })).toEqual([
      ["Diameter", "8 mm"],
      ["Height", "4 mm"],
      ["Face", "top_face"]
    ]);
  });

  it("reports countersink angles in degrees", () => {
    expect(
      operationDetails({
        operation_type: "countersink_hole",
        hole_diameter_mm: 3,
        countersink_diameter_mm: 6,
        angle_deg: 90
      })
    ).toEqual([
      ["Hole", "3 mm"],
      ["Countersink", "6 mm"],
      ["Angle", "90 deg"]
    ]);
  });

  it("summarises unknown operations without identity fields, capped at five rows", () => {
    const details = operationDetails({
      id: "op1",
      label: "ignored",
      operation_type: "mystery",
      a: 1,
      b: 2,
      c: 3,
      d: 4,
      e: 5,
      f: 6
    });
    expect(details).toHaveLength(5);
    expect(details.map(([key]) => key)).toEqual(["a", "b", "c", "d", "e"]);
  });

  it("summarises nested values rather than serialising them", () => {
    expect(operationDetails({ operation_type: "mystery", nested: { x: 1 }, list: [1, 2, 3], single: ["only"] })).toEqual([
      ["nested", "structured"],
      ["list", "3 items"],
      ["single", "1 item"]
    ]);
  });
});

describe("templateDetails", () => {
  it("omits the part type and formats remaining fields", () => {
    expect(templateDetails({ part_type: "box", length_mm: 20, holes: [{}, {}] })).toEqual([
      ["length_mm", "20"],
      ["holes", "2 items"]
    ]);
  });
});
