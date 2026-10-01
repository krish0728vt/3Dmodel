/** Keyboard shortcut registry.
 *
 *  Single source of truth so the handler, the tooltips, and the help modal can
 *  never drift apart.
 */

export type Shortcut = {
  keys: string;
  description: string;
  group: "Prompt" | "History" | "View" | "General";
  /** Whether the shortcut is suppressed while a text field has focus. */
  blockedWhileTyping: boolean;
};

export const SHORTCUTS: Shortcut[] = [
  { keys: "Ctrl+K", description: "Focus the design prompt", group: "Prompt", blockedWhileTyping: false },
  { keys: "Ctrl+Z", description: "Undo revision", group: "History", blockedWhileTyping: true },
  { keys: "Ctrl+Shift+Z", description: "Redo revision", group: "History", blockedWhileTyping: true },
  { keys: "F", description: "Fit model in view", group: "View", blockedWhileTyping: true },
  { keys: "0", description: "Isometric view", group: "View", blockedWhileTyping: true },
  { keys: "1", description: "Front view", group: "View", blockedWhileTyping: true },
  { keys: "2", description: "Right view", group: "View", blockedWhileTyping: true },
  { keys: "3", description: "Top view", group: "View", blockedWhileTyping: true },
  { keys: "Esc", description: "Clear selection, cancel tool, close overlays", group: "General", blockedWhileTyping: false },
  { keys: "?", description: "Show this shortcut list", group: "General", blockedWhileTyping: true }
];

/** True when the event target is a text-entry control.
 *
 *  Bare-letter and digit shortcuts must never fire while the user is typing a
 *  prompt or editing a dimension, which is the main hazard of single-key
 *  bindings in a form-heavy UI.
 */
export function isTextEntryTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (element === null) {
    return false;
  }
  const tag = element.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
    return true;
  }
  return element.isContentEditable === true;
}

export type ViewShortcut = "fit" | "iso" | "front" | "right" | "top";

/** Maps a bare key to a viewer action, or null when it is not a view key. */
export function viewShortcutFor(key: string): ViewShortcut | null {
  switch (key.toLowerCase()) {
    case "f":
      return "fit";
    case "0":
      return "iso";
    case "1":
      return "front";
    case "2":
      return "right";
    case "3":
      return "top";
    default:
      return null;
  }
}

/** Tooltip text with the shortcut appended, e.g. "Fit model (F)". */
export function withShortcut(label: string, keys?: string): string {
  return keys ? `${label} (${keys})` : label;
}

export function shortcutGroups(): { group: Shortcut["group"]; items: Shortcut[] }[] {
  const order: Shortcut["group"][] = ["Prompt", "History", "View", "General"];
  return order.map((group) => ({
    group,
    items: SHORTCUTS.filter((shortcut) => shortcut.group === group)
  }));
}
