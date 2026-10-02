# Changelog

## v1.0.0-rc.3

Visual refinement. The manual review of rc.2 confirmed the structure was right
but the workspace still read as an engineering debug interface: too many
controls visible at once, too many borders, and too little breathing room. This
pass trades boxes for whitespace. No functionality changed.

### Improved

- **Header reduced to identity, context and three actions.** Open, Export and
  Tools, plus a status dot. History moved to the left rail footer, the detail
  toggle into Tools, and the refresh and info icons are gone. 52 px to 60 px
  tall but far sparser.
- **Three surface levels only** (`#0b0f12`, `#11161b`, `#171d22`). Nesting a
  fourth shade was what produced the card-within-card look.
- **Named spacing scale.** Panel padding 18 px, section gap 24 px, field group
  16 px, field 8 px, button group 10 px. The old layout leaned on 4 and 8 px
  between major controls, which is what made it feel packed.
- **Borders replaced by whitespace and tint.** Hairline separators only at real
  panel boundaries; a strong border now means selection, focus or danger.
  Feature rows carry no border of their own -- selection is a background tint
  plus an accent edge.
- **Viewer controls float inside the canvas** rather than forming another
  panel: standard views upper-left, display and tools upper-right, with
  wireframe, overlays, axes, bounding box, the remaining view directions and
  focus-selection behind More.
- **Command bar is one row** of status dot, input and Send. The AI notice is a
  single thin line (`AI assistant unavailable — configure API key` plus Setup),
  Examples is a text link, and at most one notice line ever shows. Total height
  68 px, down from a stack of four layers.
- **Inspector stat rows replace micro-cards.** Revision, Parts, Mass and Issues
  were four separate bordered boxes; they are now a two-column list.
- **Assembly actions behind one menu.** Rename, Duplicate, Manifest, Archive
  and Delete were five buttons of equal weight; Delete is now explicitly
  destructive inside a menu.
- **Components collapse to a summary row** (`Base` / `Visible · Free`) and
  expand one at a time, which was the single biggest source of vertical
  clutter.
- **Collapsed rails become a narrow icon strip** instead of an empty dark
  panel, and narrow to 220/312 px below 1500 px wide rather than overflowing.
- Viewer share of window width: 70% at 1920, 63% at 1440, 61% at 1366.
- Removed 21 dead CSS rule blocks left by the rc.2 layout. The stylesheet is
  23.7 kB, down from 33.4 kB at rc.2.

### Fixed

- Frontend tests grew from 101 to 143. The new suite asserts the layout
  invariants structurally: html/body locked to the viewport, the shell as a
  100vh three-row grid, `min-height: 0` on every flexible region, scrolling
  confined to the rails and drawers, a three-action header, the spacing tokens,
  a square-only border radius, and one-at-a-time component expansion.
- Vitest now processes CSS so those assertions read the real stylesheet.

### Known Limitations

Unchanged from rc.1. The rc.3 refinement has not itself been through a
browser-based visual review; see `docs/rc-validation.md`.

## v1.0.0-rc.2

Workspace simplification. The manual visual review of rc.1 found the CAD
workspace too crowded to navigate: the prompt input sat in a 340x208 px cell in
the bottom-right corner below the fold, the project browser held a permanent
full-height column, revision history held a permanent horizontal band, and the
inspector stacked every subsystem at once. The product worked but did not read
as one. Functionality is unchanged; the interface was reorganised.

### Added

- **Persistent prompt bar.** The design assistant is now a dedicated row of the
  application shell, always visible and never inside a scrolling panel. Enter
  submits, Shift+Enter inserts a newline, Ctrl+K focuses it.
- **Drawers** for Projects, Revision History, Export and Tools. They overlay the
  workspace rather than taking a grid track, so opening one never shrinks the
  viewer.
- **Simple and Advanced detail levels**, defaulting to Simple. Advanced exposes
  parameters, relationships, component identifiers and bounding boxes. Nothing
  was removed.
- **Collapsible side rails.** Either rail collapses to hand its width straight
  to the viewer.
- **Inspector tabs**, filtered by mode: a part never shows component transform
  controls and an assembly never shows part parameters.
- `api.restoreRevision`, so the History drawer can restore a revision through
  the endpoint the backend already exposed.

### Improved

- **The page no longer scrolls.** `html, body` are `height: 100%` with
  `overflow: hidden`, and the shell is a 100vh three-row grid. Each rail, drawer
  and the prompt bar scroll internally instead. The previous
  `min-height: 100vh` let content push the document past the viewport, which is
  what produced the browser scrollbar.
- **Viewer dominance:** 71% of the window width at 1920, 61% at 1440, 59% at
  1366, and more when a rail is collapsed.
- **AI-not-configured is honest and actionable.** The box stays usable but SEND
  is disabled, the notice names `OPENAI_API_KEY`, and a Setup help action opens
  system information. A request that cannot work can no longer be sent only to
  fail with a generic parser error.
- **Assembly component card** replaced source, XYZ, rotation, bounding box and
  eight micro nudge buttons with a name, two toggles, labelled position and
  rotation fields, and an explicit Apply that is disabled until something
  changes. Identifier, source and bounding box moved behind Advanced.
- **Header** reduced from 78 px to 52 px and from a technical control strip to
  identity, context, status and five entry points. The permanent STEP and STL
  download buttons moved into the Export drawer.
- **Viewer toolbar** compacted to VIEW / DISPLAY / TOOLS with the less-used
  controls under MORE.
- **First run** asks one question, offers three ways to start, and lists the
  example prompts, pointing at the persistent bar rather than duplicating it.
- Status lines became floating toasts instead of permanent boxes.
- Frontend tests grew from 71 to 101, covering prompt gating in the configured,
  unconfigured, busy and offline states, Enter versus Shift+Enter, tab
  filtering, tab fallback when a mode changes, and drawer exclusivity.

### Fixed

- Superseded `PromptConsole` and `RevisionHistory` components removed after
  their functionality moved to `PromptBar` and `HistoryDrawer`.

### Known Limitations

Unchanged from rc.1, and still recorded in `docs/release-candidate.md`. The
rc.2 redesign has not itself been through a browser-based visual review; see
`docs/rc-validation.md`.

## v1.0.0-rc.1

First release candidate. SHAH INDUSTRIES is a local, AI-assisted parametric CAD
workspace: prompts and structured specs become validated geometry through typed
schemas and a deterministic CadQuery pipeline, with revisions, design intent,
engineering checks, assemblies, and exports.

### Added

- **One-command local deployment.** `scripts/setup.ps1` then
  `scripts/start.ps1`. Local production mode serves the app and the API from a
  single origin; development mode runs Vite with hot reload. `doctor`, `status`,
  `stop`, `build`, `clean`, and `backup` round out the launcher.
- **First-run onboarding.** Empty workspace offers create-a-part, create-an-
  assembly, and open-project, with three full example prompts.
- **Prompt lifecycle.** Seven named states (ready, interpreting, validating,
  generating, revision created, needs clarification, failed) instead of an
  opaque busy flag. No invented progress percentages.
- **Plain-language errors.** Every internal failure category maps to a titled
  explanation and a suggested fix, with the raw category and backend message
  behind a "Show details" toggle.
- **Ambiguity handling in the UI.** An under-specified edit is presented as a
  question with numbered choices rather than a generic error.
- **System/About panel.** Version, build commit, backend status, CAD engine,
  schema version, and whether AI is configured. Never exposes a key.
- **Keyboard shortcuts.** `Ctrl+K`, `Ctrl+Z`, `Ctrl+Shift+Z`, `F`, `0`/`1`/`2`/
  `3` for views, `Esc`, and `?` for the shortcut list. Bare-key bindings are
  suppressed while typing.
- **`GET /api/version`** and a `version` CLI command, both reading one source of
  truth.
- **`scripts/release_check.py`** runs the whole release gate, including the full
  benchmark and the deployment safety scan, with no network or API key.
- **`scripts/check_docs.py`** fails on broken documentation links, references to
  non-existent CLI commands, and a README over budget.

### Improved

- **Design tokens.** 78 hardcoded hex values collapsed to a small token set;
  spacing normalized onto a 4px scale. The square-cornered industrial look is
  unchanged.
- **Accessibility.** A visible `:focus-visible` indicator now exists on every
  interactive element (previously only `<textarea>` had one). Dialogs have
  roles, labels, initial focus, and Escape to close. Icon-only buttons have
  accessible names. A reduced-motion preference is respected.
- **Initial bundle: 801 kB to 301 kB** (gzip 217 kB to 90 kB). Three.js and the
  viewer are lazy-loaded behind Suspense and split into their own chunks. The
  long-standing chunk-size build warning is gone, with the threshold set just
  above the irreducible vendor chunk so a new regression still warns.
- **Benchmark corpus: 22 to 93 deterministic cases** across 18 categories, with
  a curated 28-case smoke suite that runs in about 18 seconds.
- **Viewer.** Toolbar grouped into VIEW / DISPLAY / TOOLS, tooltips name their
  shortcut, and measurement reports distance plus per-axis deltas with an
  explicit two-click flow.
- **Interference wording.** A bounding-box overlap is reported as "possible
  overlap" and says so; only a precise geometry test is called confirmed.
- **Export availability.** GLB and OBJ are shown as unsupported rather than
  offered as options that cannot work. DXF is gated on having a sketch.
- **Health endpoint** reports version and a cheap CAD-readiness flag without
  running kernel work on every poll.
- **Rename dialogs** use the in-app dialog style instead of `window.prompt`.
- API routes grouped so health and version share a `system` tag.

### Fixed

- **Memory leak in the 3D viewer.** The bounding-box helper's material was never
  disposed, leaking on every toggle and selection change, and the helper
  survived unmount. The WebGL context is now explicitly released, so repeatedly
  switching projects cannot exhaust the browser's context limit.
- **Stale responses overwriting newer state.** Switching projects quickly could
  let an earlier, slower response land last. Project, assembly, preview, and
  engineering loads are now guarded by a request-identity token.
- **Evaluation runner aborted on an invalid assembly component.** A bad
  component spec raised through the harness and ended the whole run; it is now
  recorded as a failed case.
- **A placeholder `OPENAI_API_KEY` counted as configured**, so the app claimed
  AI was available and then failed with an auth error. `.env.example` ships a
  blank key and placeholder values are treated as absent.
- Rounded corner on the System panel that broke the otherwise square UI.

### Known Limitations

- No geometric constraint solver and no SolidWorks-style mate solver. Assembly
  placement is explicit transforms.
- Selection is semantic (operation-level), not native BREP topology selection of
  individual faces and edges.
- Viewer measurements are taken against the preview mesh, so they are
  approximate rather than exact BREP distances.
- No GLB or OBJ export; no reliable local exporter exists for them.
- Backup is automated; restore is manual by design.
- Local-first and single-user. No authentication, authorization, rate limiting,
  or request auditing. Not suitable for untrusted networks.
- Natural-language behavior depends on the configured provider and model. All
  tested behavior is deterministic and does not use AI.
- Some advanced CadQuery operations have geometric limits (very large fillets,
  shells thicker than the body); these fail cleanly with an explanation.
- Docker is deferred; see [docs/deployment.md](docs/deployment.md) for why.
- No license is currently configured for this repository.
