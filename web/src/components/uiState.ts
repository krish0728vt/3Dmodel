/** Small shared presentation helpers.
 *
 *  These are pure so the wording is testable and stays consistent between the
 *  panels that use it -- the audit found the same concept phrased three
 *  different ways in different places.
 */

// ---------------------------------------------------------------------------
// Loading states
// ---------------------------------------------------------------------------

export type LoadingTask =
  | "project"
  | "model"
  | "revision"
  | "engineering"
  | "export"
  | "assembly"
  | "assembly_engineering"
  | "evaluation"
  | "capabilities";

const LOADING_LABELS: Record<LoadingTask, string> = {
  project: "LOADING PROJECT",
  model: "LOADING MODEL",
  revision: "GENERATING REVISION",
  engineering: "CALCULATING ENGINEERING DATA",
  export: "EXPORTING",
  assembly: "LOADING ASSEMBLY",
  assembly_engineering: "CALCULATING ASSEMBLY MASS",
  evaluation: "LOADING EVALUATION REPORT",
  capabilities: "LOADING CAPABILITIES"
};

/** Contextual loading label. A bare spinner tells the user nothing. */
export function loadingLabel(task: LoadingTask, detail?: string): string {
  const base = LOADING_LABELS[task];
  return detail ? `${base} - ${detail}` : base;
}

// ---------------------------------------------------------------------------
// Workspace mode
// ---------------------------------------------------------------------------

export type WorkspaceMode = "part" | "assembly" | "none";

export function workspaceMode(
  hasProject: boolean,
  hasAssembly: boolean
): WorkspaceMode {
  // An open assembly wins: component transforms are the active controls then.
  if (hasAssembly) {
    return "assembly";
  }
  return hasProject ? "part" : "none";
}

export function modeBadge(mode: WorkspaceMode): string | null {
  if (mode === "part") {
    return "PART";
  }
  if (mode === "assembly") {
    return "ASSEMBLY";
  }
  return null;
}

// ---------------------------------------------------------------------------
// Interference
// ---------------------------------------------------------------------------

/** The backend's InterferenceStatus values, verbatim. */
export type InterferenceStatus =
  | "NO_OVERLAP"
  | "POSSIBLE_OVERLAP"
  | "CONFIRMED_INTERFERENCE";

export type InterferenceInfo = {
  label: string;
  explanation: string;
  tone: "success" | "warning" | "error";
};

/**
 * Interference wording that does not overstate precision.
 *
 * A bounding-box overlap is not a collision, so POSSIBLE_OVERLAP says which
 * check produced it. Only a precise geometry test is called confirmed. The
 * `method` the backend reports is surfaced rather than assumed.
 */
export function interferenceInfo(
  status: InterferenceStatus | string,
  method?: string | null
): InterferenceInfo {
  const suffix = method ? ` (${method.replace(/_/g, " ")})` : "";
  if (status === "CONFIRMED_INTERFERENCE") {
    return {
      label: "CONFIRMED INTERFERENCE",
      explanation: `A precise geometry test found overlapping material${suffix}.`,
      tone: "error"
    };
  }
  if (status === "POSSIBLE_OVERLAP") {
    return {
      label: "POSSIBLE OVERLAP",
      explanation:
        `Bounding boxes overlap${suffix}. This is a coarse check, not a collision test; ` +
        "the solids may not actually touch.",
      tone: "warning"
    };
  }
  return {
    label: "NO OVERLAP",
    explanation: `No bounding-box overlap between components${suffix}.`,
    tone: "success"
  };
}

// ---------------------------------------------------------------------------
// Empty states
// ---------------------------------------------------------------------------

export type EmptyStateKind =
  | "revisions"
  | "assemblies"
  | "components"
  | "exports"
  | "capabilities"
  | "capability_results"
  | "evaluation"
  | "lessons"
  | "projects"
  | "search_results";

export type EmptyStateInfo = {
  message: string;
  action: string;
};

/** Every empty state names a next action; "No data" on its own is a dead end. */
const EMPTY_STATES: Record<EmptyStateKind, EmptyStateInfo> = {
  revisions: {
    message: "No revisions yet",
    action: "Describe a change in the prompt to create the first revision."
  },
  assemblies: {
    message: "No assemblies yet",
    action: "Open a part, then choose Create assembly from project."
  },
  components: {
    message: "No components yet",
    action: "Add a saved project to this assembly."
  },
  exports: {
    message: "No exports yet",
    action: "Export STEP or STL to record one here."
  },
  capabilities: {
    message: "No capabilities registered",
    action: "Run discovery against a configured source."
  },
  capability_results: {
    message: "No capability results yet",
    action: "Test an approved capability to see its output."
  },
  evaluation: {
    message: "No evaluation report yet",
    action: "Run python app.py evaluate smoke to generate one."
  },
  lessons: {
    message: "No lessons recorded yet",
    action: "Lessons appear once the Learning Core has seen enough outcomes."
  },
  projects: {
    message: "No projects yet",
    action: "Create your first part from the prompt."
  },
  search_results: {
    message: "No projects match this search",
    action: "Clear the search, or switch the status filter to All."
  }
};

export function emptyState(kind: EmptyStateKind): EmptyStateInfo {
  return EMPTY_STATES[kind];
}
