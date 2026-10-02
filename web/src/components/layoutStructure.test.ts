import { describe, expect, it } from "vitest";

// Source text is pulled in with Vite's `?raw` loader rather than node:fs, so
// the suite needs no Node typings and runs the same way the app is built.
import css from "../styles/workspace.css?raw";
import app from "../App.tsx?raw";
import viewerSource from "../viewer/CadViewer.tsx?raw";
import header from "./Header.tsx?raw";
import inspector from "./Inspector.tsx?raw";
import promptBar from "./PromptBar.tsx?raw";
import rail from "./DesignRail.tsx?raw";
import tools from "./ToolsDrawer.tsx?raw";
import { nextExpandedComponent } from "./workspaceLayout";

/**
 * Structural assertions against the real source files.
 *
 * These guard the decisions the visual review asked for -- no page scroll, a
 * sparse header, secondary actions out of the way -- in a form that fails if
 * someone reintroduces the old layout. They are not a substitute for a visual
 * review, which is recorded separately in docs/rc-validation.md.
 */


/** Collapse whitespace so declaration matching is not formatting-sensitive. */
const tight = css.replace(/\s+/g, "");

function rule(selector: string): string {
  // The declaration block for a selector, whitespace removed.
  const index = tight.indexOf(selector + "{");
  if (index === -1) {
    return "";
  }
  const start = index + selector.length + 1;
  return tight.slice(start, tight.indexOf("}", start));
}

// ---------------------------------------------------------------------------
// Global scroll
// ---------------------------------------------------------------------------

describe("global scroll is structurally prevented", () => {
  it("locks html and body to the viewport", () => {
    const block = rule("html,body");
    expect(block).toContain("height:100%");
    expect(block).toContain("overflow:hidden");
  });

  it("gives #root a full height so the shell can fill it", () => {
    expect(rule("#root")).toContain("height:100%");
  });

  it("sizes the app shell to the viewport and hides its overflow", () => {
    const block = rule(".app-shell");
    expect(block).toContain("height:100vh");
    expect(block).toContain("overflow:hidden");
  });

  it("makes the shell a three-row grid: header, work area, command bar", () => {
    expect(rule(".app-shell")).toContain("grid-template-rows:var(--header-height)minmax(0,1fr)auto");
  });

  it("gives every flexible region min-height 0 so it cannot overflow its track", () => {
    // Without this a grid child expands to its content and pushes the page.
    for (const selector of [".workspace-main", ".rail", ".stage", ".inspector-panel"]) {
      expect(rule(selector), selector).toContain("min-height:0");
    }
  });

  it("scrolls only the regions that are allowed to", () => {
    for (const selector of [".rail-scroll", ".inspector-body", ".drawer-body"]) {
      expect(rule(selector), selector).toContain("overflow-y:auto");
    }
  });

  it("keeps the command bar out of any scrolling container", () => {
    // It is a direct row of .app-shell, so it cannot be scrolled away.
    expect(app).toContain("<PromptBar");
    expect(rule(".command-bar")).not.toContain("overflow-y:auto");
  });
});

// ---------------------------------------------------------------------------
// Header is sparse
// ---------------------------------------------------------------------------

describe("header", () => {
  it("offers exactly three actions plus a status indicator", () => {
    const actions = [...header.matchAll(/className="action"/g)];
    expect(actions).toHaveLength(3);
    expect(header).toContain("Open");
    expect(header).toContain("Export");
    expect(header).toContain("Tools");
  });

  it("no longer carries History, refresh, info or the detail toggle", () => {
    // Match the imports and JSX, not prose: the file explains in a comment
    // where these moved, and that mention should not fail the check.
    const imports = header.slice(0, header.indexOf("type HeaderProps"));
    for (const icon of ["History", "RefreshCw", "Info"]) {
      expect(imports, icon).not.toContain(icon);
    }
    expect(header).not.toContain("<SystemInfo");
    expect(header).not.toContain("onOpenHistory");
    expect(header).not.toContain("onDetailLevelChange");
  });

  it("is between 56 and 64 px tall", () => {
    const match = css.match(/--header-height:\s*(\d+)px/);
    expect(match).not.toBeNull();
    const height = Number(match?.[1]);
    expect(height).toBeGreaterThanOrEqual(56);
    expect(height).toBeLessThanOrEqual(64);
  });
});

// ---------------------------------------------------------------------------
// Secondary navigation moved out of the header
// ---------------------------------------------------------------------------

describe("secondary navigation", () => {
  it("puts Projects and History in the left rail footer", () => {
    expect(rail).toContain("rail-foot");
    expect(rail).toContain("Projects");
    expect(rail).toContain("History");
  });

  it("puts the detail-level preference in the Tools drawer", () => {
    expect(tools).toContain("Detail level");
    expect(tools).toContain("segmented");
  });
});

// ---------------------------------------------------------------------------
// Whitespace, not borders
// ---------------------------------------------------------------------------

describe("spacing and surfaces", () => {
  it("defines exactly three surface levels", () => {
    expect(css).toContain("--bg-app:");
    expect(css).toContain("--bg-panel:");
    expect(css).toContain("--bg-elevated:");
  });

  it("uses a named spacing scale rather than ad-hoc pixels", () => {
    for (const token of [
      "--panel-padding:",
      "--section-gap:",
      "--field-group-gap:",
      "--field-gap:",
      "--button-gap:"
    ]) {
      expect(css, token).toContain(token);
    }
  });

  it("gives panels at least 16 px of padding", () => {
    const match = css.match(/--panel-padding:\s*(\d+)px/);
    expect(Number(match?.[1])).toBeGreaterThanOrEqual(16);
  });

  it("gives major sections at least 20 px of separation", () => {
    const match = css.match(/--section-gap:\s*(\d+)px/);
    expect(Number(match?.[1])).toBeGreaterThanOrEqual(20);
  });

  it("keeps normal UI text readable rather than shrinking to fit", () => {
    const body = css.match(/--text-body:\s*(\d+)px/);
    const value = css.match(/--text-value:\s*(\d+)px/);
    expect(Number(body?.[1])).toBeGreaterThanOrEqual(12);
    expect(Number(value?.[1])).toBeGreaterThanOrEqual(13);
  });

  it("does not use decorative gradients or glow in the shell", () => {
    expect(rule(".app-shell")).not.toContain("linear-gradient");
    expect(rule(".workspace-main")).not.toContain("linear-gradient");
  });

  it("keeps the square industrial look", () => {
    // Only circular status dots are allowed a radius.
    const radii = [...css.matchAll(/border-radius:\s*([^;]+);/g)].map((m) => m[1].trim());
    for (const radius of radii) {
      expect(radius).toBe("50%");
    }
  });

  it("selects feature rows with a tint and an accent edge, not a box", () => {
    const block = rule(".feature-row");
    expect(block).toContain("border:0");
    expect(block).toContain("border-left:2pxsolidtransparent");
    expect(rule(".feature-row.selected")).toContain("border-left-color:var(--accent)");
  });
});

// ---------------------------------------------------------------------------
// Command bar
// ---------------------------------------------------------------------------

describe("command bar", () => {
  it("is a single row of status, input and send", () => {
    expect(promptBar).toContain("command-row");
    expect(promptBar).toContain("command-input");
    expect(promptBar).toContain("command-send");
  });

  it("shows the state as a dot rather than a dedicated row", () => {
    expect(promptBar).toContain("status-dot");
    expect(rule(".status-dot")).toContain("border-radius:50%");
  });

  it("offers Examples as a text link, not a button beside Send", () => {
    expect(promptBar).toContain('className="link-action command-examples-toggle"');
  });

  it("renders at most one notice line above the input", () => {
    // error, else clarification, else the AI notice -- never stacked.
    expect(promptBar).toMatch(/error \?[\s\S]*: clarification \?[\s\S]*: !aiConfigured \?/);
  });

  it("presents the AI notice as one compact line", () => {
    expect(promptBar).toContain("AI assistant unavailable");
    expect(promptBar).toContain('className="command-line warn"');
    // A single flex line, not a bordered panel.
    const block = rule(".command-line");
    expect(block).toContain("display:flex");
    expect(block).not.toContain("border:1px");
  });

  it("keeps the input present whether or not AI is configured", () => {
    // The textarea is outside every conditional branch.
    const inputIndex = promptBar.indexOf('id="design-prompt"');
    const noticeIndex = promptBar.indexOf("AI assistant unavailable");
    expect(inputIndex).toBeGreaterThan(noticeIndex);
    expect(promptBar).not.toContain("aiConfigured ? (\n        <textarea");
  });
});

// ---------------------------------------------------------------------------
// Inspector density
// ---------------------------------------------------------------------------

describe("inspector", () => {
  it("uses two-column stat rows instead of micro-cards", () => {
    expect(inspector).toContain("stat-rows");
    expect(inspector).not.toContain("assembly-summary");
    expect(inspector).not.toContain("<Metric label=\"Revision\"");
  });

  it("puts assembly actions behind one menu", () => {
    expect(inspector).toContain("AssemblyActionsMenu");
    expect(inspector).not.toContain('className="assembly-actions"');
  });

  it("marks delete as destructive", () => {
    expect(inspector).toContain('className="menu-item destructive"');
    expect(rule(".menu-item.destructive")).toContain("color:var(--danger-text)");
  });

  it("collapses components to a summary row", () => {
    expect(inspector).toContain("component-summary");
    expect(inspector).toContain("component-state");
  });

  it("drops the micro nudge buttons entirely", () => {
    for (const token of ['"X-"', '"X+"', '"Y-"', '"Y+"', '"Z+"', '"RZ"']) {
      expect(inspector, token).not.toContain(token);
    }
  });
});

describe("single expanded component", () => {
  it("opens the clicked component", () => {
    expect(nextExpandedComponent(null, "c1")).toBe("c1");
  });

  it("closes it when clicked again", () => {
    expect(nextExpandedComponent("c1", "c1")).toBeNull();
  });

  it("replaces the open one, so only ever one is expanded", () => {
    expect(nextExpandedComponent("c1", "c2")).toBe("c2");
  });
});

// ---------------------------------------------------------------------------
// Viewer dominance
// ---------------------------------------------------------------------------

describe("viewer", () => {
  it("takes every column the rails do not", () => {
    expect(rule(".workspace-main")).toContain("grid-template-columns:236pxminmax(0,1fr)336px");
  });

  it("narrows the rails at smaller desktop widths rather than overflowing", () => {
    expect(tight).toContain("@media(max-width:1500px)");
    expect(tight).toContain("grid-template-columns:220pxminmax(0,1fr)312px");
  });

  it("collapses a rail to a narrow icon strip, not an empty panel", () => {
    expect(rule(".workspace-main.tree-collapsed")).toContain("44px");
    expect(rule(".rail-strip")).toContain("flex-direction:column");
  });

  it("floats its controls inside the canvas instead of adding a panel", () => {
    expect(rule(".viewer-overlay")).toContain("position:absolute");
    expect(css).toContain(".float-group");
  });

  it("keeps the default control set small", () => {
    const viewer = viewerSource;
    const defaultButtons = [...viewer.matchAll(/className=\{?"float-btn/g)];
    // ISO, TOP, FRONT, RIGHT, FIT, Solid, Grid, Measure, More summary.
    expect(defaultButtons.length).toBeLessThanOrEqual(10);
    // The rest moved into the menu.
    expect(viewer).toContain("float-menu");
    expect(viewer).toContain("Wireframe");
    expect(viewer).toContain("Semantic overlays");
  });
});

// ---------------------------------------------------------------------------
// One primary action per region
// ---------------------------------------------------------------------------

describe("no duplicate primary actions", () => {
  it("has a single export entry point", () => {
    // Export lives in the header and opens the drawer; no permanent STEP/STL
    // buttons anywhere in the shell.
    expect(header).not.toContain("stepHref");
    expect(header).not.toContain("stlHref");
    expect(app).toContain('toggleDrawer(current, "export")');
  });

  it("opens Projects from the header, the rail footer and the collapsed strip only", () => {
    const opens = [...app.matchAll(/setOpenDrawer\("projects"\)/g)];
    expect(opens.length).toBeLessThanOrEqual(3);
  });

  it("routes every drawer through one piece of state", () => {
    expect(app).toContain("const [openDrawer, setOpenDrawer]");
    // No parallel per-drawer booleans to drift out of sync.
    expect(app).not.toContain("showProjectsDrawer");
    expect(app).not.toContain("showToolsDrawer");
  });
});
