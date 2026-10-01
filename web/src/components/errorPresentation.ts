/** Turns backend failures into something a person can act on.
 *
 *  Internal failure categories stay technical (they are the keys the Learning
 *  Core records against), but the UI shows a plain-language title and a
 *  suggested next step. The raw category and message remain available behind a
 *  details toggle for advanced users -- never a stack trace.
 */

export type PresentedError = {
  /** Uppercase title, e.g. GEOMETRY COMBINATION FAILED. */
  title: string;
  /** Plain-language explanation of what went wrong. */
  explanation: string;
  /** Concrete thing to try next, when there is one. */
  suggestion: string | null;
  /** The internal category, shown only under "Show details". */
  category: string | null;
  /** The backend message, shown only under "Show details". */
  technical: string | null;
};

type Entry = {
  title: string;
  explanation: string;
  suggestion: string | null;
};

const CATEGORIES: Record<string, Entry> = {
  schema_error: {
    title: "REQUEST NOT UNDERSTOOD",
    explanation: "The design could not be read into a valid structure.",
    suggestion: "Rephrase the request, or enter the dimensions manually."
  },
  missing_parameter: {
    title: "MISSING DIMENSION",
    explanation: "A required dimension was not given.",
    suggestion: "Add the missing dimension and try again."
  },
  unsupported_part: {
    title: "PART TYPE NOT SUPPORTED",
    explanation: "This part type is not in the supported catalogue yet.",
    suggestion: "Try a plate, box, cylinder, spacer, bracket, or enclosure."
  },
  unsupported_operation: {
    title: "OPERATION NOT SUPPORTED",
    explanation: "That modelling operation is not available.",
    suggestion: "See the supported operation list in the design tree."
  },
  invalid_reference: {
    title: "REFERENCE NOT FOUND",
    explanation: "An operation pointed at a feature that does not exist.",
    suggestion: "Name an existing feature from the design tree."
  },
  duplicate_id: {
    title: "DUPLICATE FEATURE NAME",
    explanation: "Two operations used the same identifier.",
    suggestion: "Rename one of them."
  },
  forward_reference: {
    title: "OUT-OF-ORDER REFERENCE",
    explanation: "An operation referred to a feature created later.",
    suggestion: "Reorder the operations so the reference comes first."
  },
  invalid_geometry: {
    title: "DIMENSIONS NOT BUILDABLE",
    explanation: "The dimensions cannot produce a valid solid.",
    suggestion: "Check for zero or negative sizes, or features larger than the body."
  },
  zero_volume: {
    title: "EMPTY RESULT",
    explanation: "The operations produced no material.",
    suggestion: "Check that cuts are not removing the entire body."
  },
  boolean_failure: {
    title: "GEOMETRY COMBINATION FAILED",
    explanation: "The CAD kernel could not combine these shapes.",
    suggestion: "Make sure the shapes actually overlap, then try again."
  },
  fillet_failure: {
    title: "FILLET FAILED",
    explanation: "The requested fillet is larger than the available edge geometry.",
    suggestion: "Try reducing the radius."
  },
  chamfer_failure: {
    title: "CHAMFER FAILED",
    explanation: "The requested chamfer does not fit the available edge.",
    suggestion: "Try reducing the chamfer size."
  },
  pattern_failure: {
    title: "PATTERN FAILED",
    explanation: "The pattern could not be placed on the body.",
    suggestion: "Reduce the count or spacing so the pattern stays inside the part."
  },
  revolve_failure: {
    title: "REVOLVE FAILED",
    explanation: "The profile could not be revolved into a solid.",
    suggestion: "Check that the profile does not cross the axis of revolution."
  },
  sketch_failure: {
    title: "SKETCH FAILED",
    explanation: "The sketch could not be built into a usable profile.",
    suggestion: "Check that the sketch is closed and does not self-intersect."
  },
  loft_failure: {
    title: "LOFT FAILED",
    explanation: "The profiles could not be lofted together.",
    suggestion: "Check that every profile exists and that they are ordered along the loft."
  },
  sweep_failure: {
    title: "SWEEP FAILED",
    explanation: "The profile could not be swept along the path.",
    suggestion: "Check that the path is continuous and the profile fits around it."
  },
  shell_failure: {
    title: "SHELL FAILED",
    explanation: "The wall thickness does not fit inside the body.",
    suggestion: "Reduce the thickness, or remove a different face."
  },
  hole_feature_failure: {
    title: "HOLE FAILED",
    explanation: "The hole does not fit the body at that position.",
    suggestion: "Check the diameter, depth, and position against the part size."
  },
  engineering_analysis_failure: {
    title: "ENGINEERING ANALYSIS FAILED",
    explanation: "Mass and manufacturability data could not be calculated.",
    suggestion: "Confirm a material is selected and the geometry is a valid solid."
  },
  parametric_resolution_failure: {
    title: "PARAMETERS COULD NOT BE RESOLVED",
    explanation: "The design parameters and relationships do not produce a solution.",
    suggestion: "Review the relationships in the design tree."
  },
  dependency_cycle: {
    title: "CIRCULAR RELATIONSHIP",
    explanation: "Two or more parameters depend on each other in a loop.",
    suggestion: "Break the loop so each derived value depends only on driving values."
  },
  constraint_conflict: {
    title: "CONFLICTING CONSTRAINTS",
    explanation: "The requested values cannot all be satisfied at once.",
    suggestion: "Relax one of the conflicting values."
  },
  missing_design_parameter: {
    title: "PARAMETER NOT FOUND",
    explanation: "The edit referred to a parameter this design does not have.",
    suggestion: "Pick a parameter listed in the design tree."
  },
  assembly_reference_failure: {
    title: "COMPONENT SOURCE MISSING",
    explanation: "A component points at a project or revision that is not available.",
    suggestion: "Re-add the component from an existing project."
  },
  assembly_transform_failure: {
    title: "COMPONENT PLACEMENT INVALID",
    explanation: "The position or rotation could not be applied.",
    suggestion: "Check the transform values on the component."
  },
  assembly_interference_failure: {
    title: "INTERFERENCE CHECK FAILED",
    explanation: "The interference check could not complete.",
    suggestion: "Confirm each component has usable geometry."
  },
  assembly_export_failure: {
    title: "ASSEMBLY EXPORT FAILED",
    explanation: "The assembly could not be written in the requested format.",
    suggestion: "Try exporting components individually to find the one at fault."
  },
  capability: {
    title: "CAPABILITY CALL FAILED",
    explanation: "An external capability did not complete.",
    suggestion: "Check the capability is approved and enabled, then retry."
  },
  export_failure: {
    title: "EXPORT FAILED",
    explanation: "The file could not be written in the requested format.",
    suggestion: "Try a different format, or re-export the current revision."
  }
};

const FALLBACK: Entry = {
  title: "SOMETHING WENT WRONG",
  explanation: "The operation did not complete. Nothing was changed.",
  suggestion: "Try again. If it keeps failing, open the details below."
};

/** Backend categories arrive as `boolean_failure`; be tolerant of casing. */
function normalizeCategory(category: string | null | undefined): string | null {
  if (!category) {
    return null;
  }
  return category.trim().toLowerCase();
}

export function presentError(
  category: string | null | undefined,
  message?: string | null
): PresentedError {
  const key = normalizeCategory(category);
  const entry = (key && CATEGORIES[key]) || FALLBACK;
  return {
    title: entry.title,
    explanation: entry.explanation,
    suggestion: entry.suggestion,
    category: key,
    technical: message?.trim() ? message.trim() : null
  };
}

/** Pulls a failure category out of a backend message when one is embedded.
 *
 *  Several endpoints return `detail` strings that name the category, so this
 *  recovers it rather than always falling back to the generic title.
 */
export function inferCategory(message: string | null | undefined): string | null {
  if (!message) {
    return null;
  }
  const lowered = message.toLowerCase();
  for (const key of Object.keys(CATEGORIES)) {
    if (lowered.includes(key)) {
      return key;
    }
  }
  return null;
}

export function knownCategories(): string[] {
  return Object.keys(CATEGORIES);
}
