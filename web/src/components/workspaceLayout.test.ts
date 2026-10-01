import { describe, expect, it } from "vitest";

import {
  DEFAULT_DETAIL_LEVEL,
  defaultInspectorTab,
  inspectorTabs,
  promptGate,
  promptKeyAction,
  resolveInspectorTab,
  toggleDrawer,
  type DetailLevel
} from "./workspaceLayout";

// ---------------------------------------------------------------------------
// Detail level
// ---------------------------------------------------------------------------

describe("detail level", () => {
  it("defaults to simple", () => {
    expect(DEFAULT_DETAIL_LEVEL).toBe("simple");
  });
});

// ---------------------------------------------------------------------------
// Inspector tabs
// ---------------------------------------------------------------------------

describe("inspector tabs", () => {
  it("shows nothing when no project or assembly is open", () => {
    expect(inspectorTabs("none", "simple")).toEqual([]);
    expect(inspectorTabs("none", "advanced")).toEqual([]);
  });

  it("hides the component tab for a part", () => {
    const ids = inspectorTabs("part", "simple").map((tab) => tab.id);
    expect(ids).not.toContain("component");
    expect(ids).toContain("properties");
  });

  it("hides part parameters in assembly mode", () => {
    const ids = inspectorTabs("assembly", "advanced").map((tab) => tab.id);
    expect(ids).not.toContain("parameters");
    expect(ids).toContain("component");
  });

  it("keeps parameters behind the advanced level", () => {
    expect(inspectorTabs("part", "simple").map((t) => t.id)).not.toContain("parameters");
    expect(inspectorTabs("part", "advanced").map((t) => t.id)).toContain("parameters");
  });

  it("never shows every subsystem at once in simple mode", () => {
    // The whole point of the redesign: a short, relevant tab list.
    expect(inspectorTabs("part", "simple").length).toBeLessThanOrEqual(3);
  });

  it("defaults to properties for a part and component for an assembly", () => {
    expect(defaultInspectorTab("part")).toBe("properties");
    expect(defaultInspectorTab("assembly")).toBe("component");
  });
});

describe("resolveInspectorTab", () => {
  it("keeps a valid requested tab", () => {
    expect(resolveInspectorTab("engineering", "part", "simple")).toBe("engineering");
  });

  it("falls back when the requested tab no longer applies", () => {
    // Was editing an assembly component, then opened a part.
    expect(resolveInspectorTab("component", "part", "simple")).toBe("properties");
  });

  it("falls back when a tab is hidden by the detail level", () => {
    expect(resolveInspectorTab("parameters", "part", "simple")).toBe("properties");
    expect(resolveInspectorTab("parameters", "part", "advanced")).toBe("parameters");
  });

  it("returns null when nothing is open", () => {
    expect(resolveInspectorTab("properties", "none", "simple")).toBeNull();
  });

  it("uses the default when nothing is requested", () => {
    expect(resolveInspectorTab(null, "assembly", "simple")).toBe("component");
  });
});

// ---------------------------------------------------------------------------
// Drawers
// ---------------------------------------------------------------------------

describe("drawers", () => {
  it("opens a closed drawer", () => {
    expect(toggleDrawer(null, "projects")).toBe("projects");
  });

  it("closes the drawer that is already open", () => {
    expect(toggleDrawer("projects", "projects")).toBeNull();
  });

  it("replaces one drawer with another, so only one is open", () => {
    expect(toggleDrawer("projects", "tools")).toBe("tools");
  });
});

// ---------------------------------------------------------------------------
// Prompt gating: the AI-configured and AI-unconfigured states
// ---------------------------------------------------------------------------

describe("promptGate with AI configured", () => {
  const base = { aiConfigured: true, backendOnline: true, busy: false };

  it("enables input and SEND once there is text", () => {
    const gate = promptGate({ ...base, text: "Create a 50 mm cube." });
    expect(gate.inputEnabled).toBe(true);
    expect(gate.sendEnabled).toBe(true);
    expect(gate.reason).toBeNull();
  });

  it("keeps SEND off for empty or whitespace-only input", () => {
    expect(promptGate({ ...base, text: "" }).sendEnabled).toBe(false);
    expect(promptGate({ ...base, text: "   \n  " }).sendEnabled).toBe(false);
  });

  it("does not nag about empty input", () => {
    // No reason text for the ordinary idle state.
    expect(promptGate({ ...base, text: "" }).reason).toBeNull();
  });

  it("blocks SEND while a request is in flight but keeps the box usable", () => {
    const gate = promptGate({ ...base, busy: true, text: "another request" });
    expect(gate.sendEnabled).toBe(false);
    expect(gate.inputEnabled).toBe(true);
    expect(gate.reason).toContain("previous request");
  });
});

describe("promptGate with AI not configured", () => {
  const unconfigured = {
    aiConfigured: false,
    backendOnline: true,
    busy: false,
    text: "Create a 50 mm cube."
  };

  it("disables SEND even with valid text", () => {
    // The user must not be able to send a request that cannot work and then
    // collect a confusing generic failure.
    expect(promptGate(unconfigured).sendEnabled).toBe(false);
  });

  it("explains why, naming the variable to set", () => {
    const reason = promptGate(unconfigured).reason ?? "";
    expect(reason).toContain("OPENAI_API_KEY");
    expect(reason.toLowerCase()).toContain("not configured");
  });

  it("still allows typing, so the box is not dead", () => {
    expect(promptGate(unconfigured).inputEnabled).toBe(true);
  });
});

describe("promptGate with the backend offline", () => {
  it("disables both input and SEND and says so", () => {
    const gate = promptGate({
      aiConfigured: true,
      backendOnline: false,
      busy: false,
      text: "anything"
    });
    expect(gate.inputEnabled).toBe(false);
    expect(gate.sendEnabled).toBe(false);
    expect(gate.reason).toContain("offline");
  });

  it("reports offline ahead of the AI key, since it blocks everything", () => {
    const gate = promptGate({
      aiConfigured: false,
      backendOnline: false,
      busy: false,
      text: "x"
    });
    expect(gate.reason).toContain("offline");
  });
});

// ---------------------------------------------------------------------------
// Enter / Shift+Enter
// ---------------------------------------------------------------------------

describe("promptKeyAction", () => {
  it("submits on Enter", () => {
    expect(promptKeyAction({ key: "Enter", shiftKey: false })).toBe("submit");
  });

  it("inserts a newline on Shift+Enter", () => {
    expect(promptKeyAction({ key: "Enter", shiftKey: true })).toBe("newline");
  });

  it("ignores every other key", () => {
    for (const key of ["a", "Escape", "Tab", "ArrowUp", " "]) {
      expect(promptKeyAction({ key, shiftKey: false })).toBe("ignore");
    }
  });

  it("does not submit when Ctrl or Cmd is held", () => {
    // Ctrl+Enter is a common "send" elsewhere, but here it must not
    // double-fire alongside the plain Enter binding.
    expect(promptKeyAction({ key: "Enter", shiftKey: false, ctrlKey: true })).toBe("ignore");
    expect(promptKeyAction({ key: "Enter", shiftKey: false, metaKey: true })).toBe("ignore");
  });
});

// ---------------------------------------------------------------------------
// Layout invariants the redesign has to hold
// ---------------------------------------------------------------------------

describe("layout invariants", () => {
  it("offers a short tab list at every mode and level combination", () => {
    const modes = ["part", "assembly"] as const;
    const levels: DetailLevel[] = ["simple", "advanced"];
    for (const mode of modes) {
      for (const level of levels) {
        const tabs = inspectorTabs(mode, level);
        expect(tabs.length).toBeGreaterThan(0);
        // Short enough to read at a glance rather than a stack of subsystems.
        expect(tabs.length).toBeLessThanOrEqual(4);
      }
    }
  });

  it("always resolves to a tab that exists in the current list", () => {
    const modes = ["part", "assembly"] as const;
    const levels: DetailLevel[] = ["simple", "advanced"];
    const requests = [
      null,
      "properties",
      "component",
      "engineering",
      "assembly",
      "parameters"
    ] as const;
    for (const mode of modes) {
      for (const level of levels) {
        const available = inspectorTabs(mode, level).map((tab) => tab.id);
        for (const requested of requests) {
          const resolved = resolveInspectorTab(requested, mode, level);
          expect(resolved).not.toBeNull();
          expect(available).toContain(resolved);
        }
      }
    }
  });
});
