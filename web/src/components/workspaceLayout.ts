/** Workspace layout rules.
 *
 *  Pure so the decisions that drive the redesign -- which inspector sections
 *  are visible, whether the prompt can be submitted, which panels are open --
 *  are testable without mounting the app.
 */

import type { WorkspaceMode } from "./uiState";

// ---------------------------------------------------------------------------
// Simple / Advanced
// ---------------------------------------------------------------------------

export type DetailLevel = "simple" | "advanced";

export const DEFAULT_DETAIL_LEVEL: DetailLevel = "simple";

// ---------------------------------------------------------------------------
// Inspector tabs
// ---------------------------------------------------------------------------

export type InspectorTab =
  | "properties"
  | "component"
  | "engineering"
  | "assembly"
  | "parameters";

export type TabDefinition = {
  id: InspectorTab;
  label: string;
  /** Only shown at the advanced detail level. */
  advancedOnly: boolean;
};

const ALL_TABS: TabDefinition[] = [
  { id: "properties", label: "Properties", advancedOnly: false },
  { id: "component", label: "Component", advancedOnly: false },
  { id: "engineering", label: "Engineering", advancedOnly: false },
  { id: "assembly", label: "Assembly", advancedOnly: false },
  { id: "parameters", label: "Parameters", advancedOnly: true }
];

/**
 * Which inspector tabs apply right now.
 *
 * The old inspector stacked every subsystem at once. Tabs are filtered by
 * workspace mode so a part never shows component-transform controls and an
 * assembly never shows part parameters.
 */
export function inspectorTabs(mode: WorkspaceMode, level: DetailLevel): TabDefinition[] {
  if (mode === "none") {
    return [];
  }
  return ALL_TABS.filter((tab) => {
    if (tab.advancedOnly && level !== "advanced") {
      return false;
    }
    if (mode === "part") {
      // A part has no component transform to edit.
      return tab.id !== "component";
    }
    // Assembly mode: parameters belong to the source parts, not the assembly.
    return tab.id !== "parameters";
  });
}

/** The tab shown when a mode is entered: Properties for a part, Component for an assembly. */
export function defaultInspectorTab(mode: WorkspaceMode): InspectorTab {
  return mode === "assembly" ? "component" : "properties";
}

/**
 * Keeps the active tab valid when the mode or detail level changes.
 *
 * Switching from assembly to part while "Component" is active would otherwise
 * leave the inspector on a tab that no longer exists.
 */
export function resolveInspectorTab(
  requested: InspectorTab | null,
  mode: WorkspaceMode,
  level: DetailLevel
): InspectorTab | null {
  const available = inspectorTabs(mode, level);
  if (available.length === 0) {
    return null;
  }
  if (requested && available.some((tab) => tab.id === requested)) {
    return requested;
  }
  const fallback = defaultInspectorTab(mode);
  return available.some((tab) => tab.id === fallback) ? fallback : available[0].id;
}

// ---------------------------------------------------------------------------
// Drawers
// ---------------------------------------------------------------------------

export type DrawerName = "projects" | "history" | "export" | "tools" | "shortcuts";

/** Drawers overlay the workspace, so only one is open at a time. */
export function toggleDrawer(current: DrawerName | null, requested: DrawerName): DrawerName | null {
  return current === requested ? null : requested;
}

// ---------------------------------------------------------------------------
// Prompt submission
// ---------------------------------------------------------------------------

export type PromptGate = {
  /** Whether the textarea accepts input. */
  inputEnabled: boolean;
  /** Whether SEND is actionable. */
  sendEnabled: boolean;
  /** Why SEND is unavailable, for the tooltip and the visible notice. */
  reason: string | null;
};

/**
 * Whether a request can be sent right now.
 *
 * Without an API key the box is left visible but SEND is disabled and the
 * reason is stated, so a user cannot type a request and then collect a
 * confusing generic failure from the parser.
 */
export function promptGate(options: {
  aiConfigured: boolean;
  backendOnline: boolean;
  busy: boolean;
  text: string;
}): PromptGate {
  const { aiConfigured, backendOnline, busy, text } = options;

  if (!backendOnline) {
    return {
      inputEnabled: false,
      sendEnabled: false,
      reason: "The backend is offline. Natural-language requests need a running server."
    };
  }
  if (!aiConfigured) {
    return {
      inputEnabled: true,
      sendEnabled: false,
      reason:
        "AI assistant not configured. Set OPENAI_API_KEY in .env to enable natural-language design."
    };
  }
  if (busy) {
    return { inputEnabled: true, sendEnabled: false, reason: "Working on the previous request." };
  }
  if (text.trim().length === 0) {
    return { inputEnabled: true, sendEnabled: false, reason: null };
  }
  return { inputEnabled: true, sendEnabled: true, reason: null };
}

/**
 * How a keypress in the prompt should be handled.
 *
 * Enter submits and Shift+Enter inserts a newline, which is the convention for
 * a chat-style command bar.
 */
export type PromptKeyAction = "submit" | "newline" | "ignore";

export function promptKeyAction(event: {
  key: string;
  shiftKey: boolean;
  ctrlKey?: boolean;
  metaKey?: boolean;
}): PromptKeyAction {
  if (event.key !== "Enter") {
    return "ignore";
  }
  // A modifier other than Shift should not submit either; let the browser be.
  if (event.ctrlKey || event.metaKey) {
    return "ignore";
  }
  return event.shiftKey ? "newline" : "submit";
}


// ---------------------------------------------------------------------------
// Assembly component accordion
// ---------------------------------------------------------------------------

/**
 * Which component should be expanded after a click.
 *
 * Exactly one at a time: a fully expanded component list was the single
 * biggest source of vertical clutter in the inspector.
 */
export function nextExpandedComponent(
  current: string | null,
  clicked: string
): string | null {
  return current === clicked ? null : clicked;
}
