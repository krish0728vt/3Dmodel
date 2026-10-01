/** Prompt console lifecycle.
 *
 *  Deliberately a small set of named states rather than a progress percentage:
 *  the backend reports stage transitions, not completion fractions, and a fake
 *  percentage would be inventing information we do not have.
 */
export type PromptState =
  | "ready"
  | "interpreting"
  | "validating"
  | "generating"
  | "revision_created"
  | "needs_clarification"
  | "failed";

export type PromptStateInfo = {
  /** Short uppercase label shown next to the prompt. */
  label: string;
  /** One line explaining what is happening or what to do next. */
  hint: string;
  /** True while work is in flight, so the UI can disable submission. */
  busy: boolean;
  /** Drives the status dot styling. */
  tone: "idle" | "active" | "success" | "attention" | "error";
};

const STATES: Record<PromptState, PromptStateInfo> = {
  ready: {
    label: "READY",
    hint: "Describe what you want to build.",
    busy: false,
    tone: "idle"
  },
  interpreting: {
    label: "INTERPRETING",
    hint: "Reading your request into a structured design.",
    busy: true,
    tone: "active"
  },
  validating: {
    label: "VALIDATING",
    hint: "Checking dimensions and operations before building geometry.",
    busy: true,
    tone: "active"
  },
  generating: {
    label: "GENERATING",
    hint: "Building geometry with the CAD kernel.",
    busy: true,
    tone: "active"
  },
  revision_created: {
    label: "REVISION CREATED",
    hint: "Geometry built and saved as a new revision.",
    busy: false,
    tone: "success"
  },
  needs_clarification: {
    label: "NEEDS CLARIFICATION",
    hint: "The request matched more than one thing. Pick which one you meant.",
    busy: false,
    tone: "attention"
  },
  failed: {
    label: "FAILED",
    hint: "Nothing was changed. See the details below.",
    busy: false,
    tone: "error"
  }
};

export function promptStateInfo(state: PromptState): PromptStateInfo {
  return STATES[state];
}

export function isPromptBusy(state: PromptState): boolean {
  return STATES[state].busy;
}

/** Every state, in lifecycle order. Used by the tests to guard the set. */
export const PROMPT_STATES: PromptState[] = [
  "ready",
  "interpreting",
  "validating",
  "generating",
  "revision_created",
  "needs_clarification",
  "failed"
];
