import { describe, expect, it } from "vitest";

import { EXAMPLE_PROMPTS } from "./EmptyWorkspace";
import { inferCategory, knownCategories, presentError } from "./errorPresentation";
import { PROMPT_STATES, isPromptBusy, promptStateInfo } from "./promptState";
import {
  SHORTCUTS,
  isTextEntryTarget,
  shortcutGroups,
  viewShortcutFor,
  withShortcut
} from "./shortcuts";
import {
  emptyState,
  interferenceInfo,
  loadingLabel,
  modeBadge,
  workspaceMode
} from "./uiState";

// ---------------------------------------------------------------------------
// Onboarding
// ---------------------------------------------------------------------------

describe("onboarding examples", () => {
  it("offers three full-sentence prompts", () => {
    expect(EXAMPLE_PROMPTS).toHaveLength(3);
    for (const example of EXAMPLE_PROMPTS) {
      expect(example.endsWith(".")).toBe(true);
      // Full requests, not two-word labels.
      expect(example.split(" ").length).toBeGreaterThan(5);
    }
  });

  it("includes a dimensioned mounting plate example", () => {
    const plate = EXAMPLE_PROMPTS.find((example) => example.includes("mounting plate"));
    expect(plate).toBeDefined();
    expect(plate).toContain("mm");
  });
});

// ---------------------------------------------------------------------------
// Prompt lifecycle
// ---------------------------------------------------------------------------

describe("prompt state", () => {
  it("covers the seven lifecycle states", () => {
    expect(PROMPT_STATES).toEqual([
      "ready",
      "interpreting",
      "validating",
      "generating",
      "revision_created",
      "needs_clarification",
      "failed"
    ]);
  });

  it("marks only in-flight states busy", () => {
    expect(isPromptBusy("interpreting")).toBe(true);
    expect(isPromptBusy("validating")).toBe(true);
    expect(isPromptBusy("generating")).toBe(true);
    expect(isPromptBusy("ready")).toBe(false);
    expect(isPromptBusy("revision_created")).toBe(false);
    expect(isPromptBusy("needs_clarification")).toBe(false);
    expect(isPromptBusy("failed")).toBe(false);
  });

  it("gives every state an uppercase label and a hint", () => {
    for (const state of PROMPT_STATES) {
      const info = promptStateInfo(state);
      expect(info.label).toBe(info.label.toUpperCase());
      expect(info.hint.length).toBeGreaterThan(0);
    }
  });

  it("distinguishes clarification from failure", () => {
    expect(promptStateInfo("needs_clarification").tone).toBe("attention");
    expect(promptStateInfo("failed").tone).toBe("error");
  });

  it("states that nothing changed on failure", () => {
    expect(promptStateInfo("failed").hint.toLowerCase()).toContain("nothing was changed");
  });
});

// ---------------------------------------------------------------------------
// Error presentation
// ---------------------------------------------------------------------------

describe("error presentation", () => {
  it("maps a boolean failure to plain language", () => {
    const presented = presentError("boolean_failure", "OCC boolean op returned null");
    expect(presented.title).toBe("GEOMETRY COMBINATION FAILED");
    expect(presented.explanation).toContain("could not combine");
    expect(presented.suggestion).toBeTruthy();
    // The internal category stays available for the details toggle.
    expect(presented.category).toBe("boolean_failure");
    expect(presented.technical).toBe("OCC boolean op returned null");
  });

  it("gives the fillet case an actionable suggestion", () => {
    const presented = presentError("fillet_failure");
    expect(presented.explanation).toContain("larger than the available edge");
    expect(presented.suggestion).toContain("reducing the radius");
  });

  it("falls back without inventing a cause", () => {
    const presented = presentError("something_brand_new", "backend said no");
    expect(presented.title).toBe("SOMETHING WENT WRONG");
    expect(presented.category).toBe("something_brand_new");
    expect(presented.technical).toBe("backend said no");
  });

  it("handles a missing category and message", () => {
    const presented = presentError(null);
    expect(presented.title).toBe("SOMETHING WENT WRONG");
    expect(presented.category).toBeNull();
    expect(presented.technical).toBeNull();
  });

  it("treats a blank message as absent rather than showing an empty detail", () => {
    expect(presentError("export_failure", "   ").technical).toBeNull();
  });

  it("tolerates casing and surrounding whitespace", () => {
    expect(presentError("  BOOLEAN_FAILURE  ").title).toBe("GEOMETRY COMBINATION FAILED");
  });

  it("recovers a category embedded in a backend message", () => {
    expect(inferCategory("Operation failed: shell_failure on body1")).toBe("shell_failure");
    expect(inferCategory("no category here")).toBeNull();
    expect(inferCategory(null)).toBeNull();
  });

  it("covers every category with a distinct title", () => {
    const categories = knownCategories();
    expect(categories.length).toBeGreaterThanOrEqual(25);
    for (const category of categories) {
      const presented = presentError(category);
      expect(presented.title).not.toBe("SOMETHING WENT WRONG");
      // Titles are uppercase and never leak the raw snake_case key.
      expect(presented.title).toBe(presented.title.toUpperCase());
      expect(presented.title).not.toContain("_");
    }
  });
});

// ---------------------------------------------------------------------------
// Loading and empty states
// ---------------------------------------------------------------------------

describe("loading labels", () => {
  it("names the work rather than spinning anonymously", () => {
    expect(loadingLabel("project")).toBe("LOADING PROJECT");
    expect(loadingLabel("engineering")).toBe("CALCULATING ENGINEERING DATA");
    expect(loadingLabel("revision")).toBe("GENERATING REVISION");
  });

  it("appends a detail when given one", () => {
    expect(loadingLabel("export", "STEP")).toBe("EXPORTING - STEP");
  });
});

describe("empty states", () => {
  it("always offers a next action", () => {
    const kinds = [
      "revisions",
      "assemblies",
      "components",
      "exports",
      "capabilities",
      "capability_results",
      "evaluation",
      "lessons",
      "projects",
      "search_results"
    ] as const;
    for (const kind of kinds) {
      const info = emptyState(kind);
      expect(info.message.length).toBeGreaterThan(0);
      expect(info.action.length).toBeGreaterThan(0);
    }
  });

  it("distinguishes no projects from no search matches", () => {
    expect(emptyState("projects").message).toBe("No projects yet");
    expect(emptyState("search_results").action).toContain("Clear the search");
  });
});

// ---------------------------------------------------------------------------
// Mode
// ---------------------------------------------------------------------------

describe("workspace mode", () => {
  it("reports part, assembly, or neither", () => {
    expect(workspaceMode(true, false)).toBe("part");
    expect(workspaceMode(true, true)).toBe("assembly");
    expect(workspaceMode(false, false)).toBe("none");
  });

  it("badges only a real mode", () => {
    expect(modeBadge("part")).toBe("PART");
    expect(modeBadge("assembly")).toBe("ASSEMBLY");
    expect(modeBadge("none")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Interference
// ---------------------------------------------------------------------------

describe("interference wording", () => {
  it("does not call a bounding-box overlap a collision", () => {
    const possible = interferenceInfo("POSSIBLE_OVERLAP", "bounding_box");
    expect(possible.label).toBe("POSSIBLE OVERLAP");
    expect(possible.explanation).toContain("Bounding boxes");
    expect(possible.explanation).toContain("not a collision test");
    expect(possible.tone).toBe("warning");
  });

  it("names the method the backend reported", () => {
    expect(interferenceInfo("POSSIBLE_OVERLAP", "bounding_box").explanation).toContain(
      "bounding box"
    );
    expect(interferenceInfo("CONFIRMED_INTERFERENCE", "precise_solid").explanation).toContain(
      "precise solid"
    );
  });

  it("reserves confirmed for a precise test", () => {
    const confirmed = interferenceInfo("CONFIRMED_INTERFERENCE");
    expect(confirmed.label).toBe("CONFIRMED INTERFERENCE");
    expect(confirmed.explanation).toContain("precise geometry test");
    expect(confirmed.tone).toBe("error");
  });

  it("reports no overlap as success", () => {
    expect(interferenceInfo("NO_OVERLAP").label).toBe("NO OVERLAP");
    expect(interferenceInfo("NO_OVERLAP").tone).toBe("success");
  });

  it("falls back to no-overlap for an unrecognized status", () => {
    // Safer to understate than to claim a collision we cannot support.
    expect(interferenceInfo("SOMETHING_NEW").tone).toBe("success");
  });

  it("omits the method suffix when none is given", () => {
    expect(interferenceInfo("NO_OVERLAP").explanation).not.toContain("(");
  });
});

// ---------------------------------------------------------------------------
// Shortcuts
// ---------------------------------------------------------------------------

describe("shortcuts", () => {
  it("blocks every bare-key shortcut while typing", () => {
    // A single letter or digit must not fire mid-prompt.
    for (const shortcut of SHORTCUTS) {
      const isBareKey = !shortcut.keys.includes("+") && shortcut.keys !== "Esc";
      if (isBareKey) {
        expect(shortcut.blockedWhileTyping).toBe(true);
      }
    }
  });

  it("keeps Ctrl+K and Esc available while typing", () => {
    const focus = SHORTCUTS.find((shortcut) => shortcut.keys === "Ctrl+K");
    const escape = SHORTCUTS.find((shortcut) => shortcut.keys === "Esc");
    expect(focus?.blockedWhileTyping).toBe(false);
    expect(escape?.blockedWhileTyping).toBe(false);
  });

  it("detects text-entry targets", () => {
    for (const tag of ["INPUT", "TEXTAREA", "SELECT"]) {
      expect(isTextEntryTarget({ tagName: tag } as unknown as EventTarget)).toBe(true);
    }
    expect(isTextEntryTarget({ tagName: "BUTTON" } as unknown as EventTarget)).toBe(false);
    expect(isTextEntryTarget(null)).toBe(false);
  });

  it("treats a contenteditable element as text entry", () => {
    const editable = { tagName: "DIV", isContentEditable: true } as unknown as EventTarget;
    expect(isTextEntryTarget(editable)).toBe(true);
  });

  it("maps the view keys", () => {
    expect(viewShortcutFor("f")).toBe("fit");
    expect(viewShortcutFor("F")).toBe("fit");
    expect(viewShortcutFor("0")).toBe("iso");
    expect(viewShortcutFor("1")).toBe("front");
    expect(viewShortcutFor("2")).toBe("right");
    expect(viewShortcutFor("3")).toBe("top");
    expect(viewShortcutFor("q")).toBeNull();
    expect(viewShortcutFor("9")).toBeNull();
  });

  it("builds tooltips with the shortcut appended", () => {
    expect(withShortcut("Fit model", "F")).toBe("Fit model (F)");
    expect(withShortcut("Top view")).toBe("Top view");
  });

  it("groups shortcuts without losing any", () => {
    const grouped = shortcutGroups();
    const total = grouped.reduce((sum, entry) => sum + entry.items.length, 0);
    expect(total).toBe(SHORTCUTS.length);
    expect(grouped.map((entry) => entry.group)).toEqual(["Prompt", "History", "View", "General"]);
  });

  it("has no duplicate bindings", () => {
    const keys = SHORTCUTS.map((shortcut) => shortcut.keys);
    expect(new Set(keys).size).toBe(keys.length);
  });
});
