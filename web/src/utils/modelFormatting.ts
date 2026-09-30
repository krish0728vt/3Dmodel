const operationNames: Record<string, string> = {
  create_box: "Box",
  create_cylinder: "Cylinder",
  create_sketch: "Sketch",
  create_sketch_rectangle: "Rectangle Sketch",
  create_sketch_circle: "Circle Sketch",
  extrude: "Extrude",
  cut_extrude: "Pocket",
  revolve: "Revolve",
  loft: "Loft",
  sweep: "Sweep",
  shell: "Shell",
  through_hole: "Through Hole",
  blind_hole: "Blind Hole",
  counterbore_hole: "Counterbore",
  countersink_hole: "Countersink",
  boss: "Boss",
  rib: "Rib",
  rectangular_hole_pattern: "Rectangular Hole Pattern",
  circular_hole_pattern: "Circular Hole Pattern",
  cut_hole: "Hole",
  boolean_union: "Union",
  boolean_cut: "Cut",
  fillet: "Fillet",
  chamfer: "Chamfer",
  linear_pattern: "Linear Pattern",
  circular_pattern: "Circular Pattern",
  mirror: "Mirror"
};

export function operationDisplayName(operation: Record<string, unknown>): string {
  const label = operation.label;
  if (typeof label === "string" && label.trim()) {
    return label;
  }
  const type = String(operation.operation_type ?? "operation");
  return operationNames[type] ?? type.replaceAll("_", " ");
}

export function operationKind(operation: Record<string, unknown>): string {
  const type = String(operation.operation_type ?? "operation");
  return operationNames[type] ?? type.replaceAll("_", " ");
}

export function operationDetails(operation: Record<string, unknown>): Array<[string, string]> {
  const type = String(operation.operation_type ?? "");
  if (type === "loft") {
    return [
      ["Profiles", asList(operation.sketch_ids)],
      ["Ruled", String(operation.ruled ?? false)]
    ];
  }
  if (type === "sweep") {
    return [
      ["Profile", String(operation.profile_sketch_id ?? "")],
      ["Path", String(operation.path_sketch_id ?? "")]
    ];
  }
  if (type === "shell") {
    return [
      ["Target", String(operation.target_id ?? "")],
      ["Thickness", mm(operation.thickness_mm)],
      ["Removed Face", String(operation.remove_face_selector ?? "none")]
    ];
  }
  if (type === "cut_extrude") {
    return [
      ["Target", String(operation.target_id ?? "")],
      ["Sketch", String(operation.sketch_id ?? "")],
      ["Distance", operation.extent_type === "through_all" ? "through all" : mm(operation.distance_mm)]
    ];
  }
  if (type === "countersink_hole") {
    return [
      ["Hole", mm(operation.hole_diameter_mm)],
      ["Countersink", mm(operation.countersink_diameter_mm)],
      ["Angle", degrees(operation.angle_deg)]
    ];
  }
  if (type === "counterbore_hole") {
    return [
      ["Hole", mm(operation.hole_diameter_mm)],
      ["Counterbore", mm(operation.counterbore_diameter_mm)],
      ["Depth", mm(operation.counterbore_depth_mm)]
    ];
  }
  if (type === "boss") {
    return [
      ["Diameter", mm(operation.diameter_mm)],
      ["Height", mm(operation.height_mm)],
      ["Face", String(operation.face_selector ?? "top_face")]
    ];
  }
  if (type === "rib") {
    return [
      ["Thickness", mm(operation.thickness_mm)],
      ["Height", mm(operation.height_mm)]
    ];
  }
  return Object.entries(operation)
    .filter(([key]) => !["id", "label", "operation_type"].includes(key))
    .slice(0, 5)
    .map(([key, value]) => [key, formatValue(value)]);
}

export function templateDetails(model: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(model)
    .filter(([key]) => key !== "part_type")
    .map(([key, value]) => [key, formatValue(value)]);
}

function asList(value: unknown): string {
  return Array.isArray(value) ? value.join(", ") : String(value ?? "");
}

function mm(value: unknown): string {
  return typeof value === "number" ? `${value} mm` : `${String(value ?? "")} mm`;
}

function degrees(value: unknown): string {
  return typeof value === "number" ? `${value} deg` : `${String(value ?? "")} deg`;
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) {
    return `${value.length} item${value.length === 1 ? "" : "s"}`;
  }
  if (typeof value === "object" && value !== null) {
    return "structured";
  }
  return String(value);
}
