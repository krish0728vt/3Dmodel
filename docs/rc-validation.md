# Release Candidate Validation

## Summary

| Field | Value |
| --- | --- |
| Validation date | 2026-10-01 |
| Starting commit | `6e4a7e3` |
| Starting tag | `v1.0.0-rc.1` |
| Version under test | 1.0.0-rc.1 |
| Candidate now | **v1.0.0-rc.2** |
| Release blockers | 1 found, 1 fixed |
| Decision | **RC2 PRODUCED - READY FOR v1.0.0 AFTER DOCUMENTED MANUAL VISUAL CHECK OF RC2** |

RC1 was tagged without a validation pass having been run; the first part of this
document is that pass. Every functional, deterministic and safety gate passed.

The manual visual review was then **performed by the maintainer** and found a
release-quality usability defect in the CAD workspace. That is recorded below
and was fixed, producing **v1.0.0-rc.2**. `v1.0.0-rc.1` and commit `6e4a7e3`
were left untouched.

## Environment

| Component | Version |
| --- | --- |
| OS | Windows 11 Home 10.0.26100 |
| Python | 3.11.9 (`.venv311`) |
| CadQuery | 2.8.0, OpenCascade geometry verified |
| Node.js | 24.14.0, npm 11.9.0 |
| Browser automation | **none available** (see Visual Review) |

All validation ran against isolated temporary databases and output directories.
The developer's own `data/` stores were never written to. No AI was used; no
network calls were made beyond the GitHub Actions status query.

## What was validated

### Real-world designs (Phase 4)

Ten designs authored specifically for this pass, with dimensions and feature
combinations deliberately different from the benchmark fixtures, so the suite
was not validating itself. **90/90 checks passed.**

Simple mounting plate, four-corner-hole plate, electronics enclosure,
L-bracket, pocketed plate, countersunk plate, shelled open tray, lofted
adapter, swept tube, slotted bracket.

Each was checked for: spec validation, geometry generation, bounding box
against an independently computed expectation, volume against an analytic
expectation where one exists, single-solid topology, STEP export with a valid
ISO-10303-21 header, STL export, spec round-trip stability, and **STEP
re-import** — the exported file was read back with CadQuery and its bounding box
and volume compared against the original. Every re-import matched exactly.

### Parametric relationship preservation (Phase 5)

| Workflow | Result |
| --- | --- |
| Plate 100→140 mm wide, holes 8 mm from edges | Offset held at exactly 8.0 mm; hole X moved −42 → −62, confirming real recalculation rather than a stale value |
| Centered boss, base 80×80 → 120×100 | Boss stayed at (0, 0) |
| Derived hole pitch, width 120 → 180 | Pitch recalculated 30 → 45 mm |
| Enclosure derived from PCB width 80 → 100 | Inner width tracked 88 → 108 mm; shelled geometry followed |

### Multi-edit workflow and revision lineage (Phase 6)

Create → widen → enlarge hole → add fillet → change material → undo ×2 →
redo ×2 → restore REV 2 → branch. All 20 checks passed. The properties that
matter most:

- Revision lineage is a correct chain (1 → 2 → 3 → 4).
- **Undo and redo left all four stored revision specs byte-identical.**
- Every revision still rebuilds to the geometry it recorded.
- Branching from REV 2 created REV 5 with the right parent and **did not mutate
  REV 4**.
- Changing material did not create a spurious revision.

### Assembly workflow and source immutability (Phases 7 and 8)

A five-component assembly (base plate, enclosure, lid, PCB placeholder,
bracket) with grounding, translation and rotation. All 17 checks passed.

The critical test: after moving one component and rotating another, **all five
source projects were unchanged** — same revision number, byte-identical spec,
identical rebuilt geometry, and no extra revisions. Assembly STEP export
(168 kB) and a 5-component manifest both produced.

Interference reported `POSSIBLE_OVERLAP` by method `world_bounding_box_overlap`
for the nested PCB, which is the honest label for a coarse check.

### Assembly mass aggregation

The headline assembly reported `0.0 g` with five unknown-mass components, which
is correct when no material is assigned. Verified separately that aggregation
works:

| Case | Result |
| --- | --- |
| Three aluminium cubes | 64.80 g, matching 3 × 8 cm³ × 2.70 g/cm³ exactly; centre of mass available |
| Two assigned, one not | 84.40 g known, the unassigned component listed as unknown |
| None assigned | 0 g accompanied by the full unknown list, not presented as a real total |

### Exports (Phases 9, 10, 11)

27/27 checks passed. STEP, STL at draft/standard/high (15 kB / 51 kB / 145 kB,
correctly increasing), DXF, manifest, and ZIP.

- Every reported SHA-256 checksum was recomputed from the bytes on disk and
  matched.
- Filenames are safe and carry the revision (`RC_Export_Plate_rev_001.step`).
- ZIP archives are intact, contain geometry plus manifest, and have no
  traversal paths in their entry names.
- DXF from a structured sketch contains real `LINE`/`POLYLINE` geometry.
- The manifest contains no secret.
- **GLB and OBJ are refused with an `ExportError`**, not silently faked.
- STEP metadata already carries an internal round-trip volume check.

### Lifecycle isolation (Phases 12 and 13)

27/27 checks passed: create, rename, duplicate, archive, unarchive, search,
all four sort orders, and recent-project marking, for both projects and
assemblies.

The isolation test: deleting one project left the other three **byte-identical**
in both metadata and stored specs, and deleting an assembly left all projects
intact.

### Capability safety (Phase 26)

14/14 checks passed. The gate is stronger than expected — it has four stages,
not two:

1. A newly discovered capability is neither approved nor enabled.
2. Invocation while unapproved is refused.
3. **`approve()` itself refuses until the capability passes a self-test**
   ("Capability must pass self-test before approval").
4. Approval does not imply enablement; invocation while disabled is refused.

Only after self-test → approve → enable does the local spur gear run. Invalid
input (negative teeth, zero module, a missing field) is rejected even when
enabled, and disabling takes effect immediately. No auto-approval anywhere.

### Learning Core (Phase 27)

Verified behaviourally: failure classification maps a kernel message to
`FILLET_FAILURE`; failures are recorded and retrievable; lesson retrieval
surfaces a stored lesson; repair attempts are recorded; analytics aggregate by
category; revalidation marking preserved every record. Lesson evidence
accumulated correctly and promoted `OBSERVED` → `VALIDATED` on the fourth
success, matching the configured threshold of three.

### API error review (Phase 25)

37/37 checks passed. Ten expected-failure probes (unknown project, unknown
revision, unknown assembly, unknown capability, negative dimension, neither
prompt nor spec, unknown part type, unsupported export format, unknown
material, unknown parameter). For every one:

- the status code was in the expected range,
- the body was structured JSON,
- **no traceback leaked to the client.**

Messages are written for a person: *"Project not found."*, *"Invalid mounting
plate specification: width_mm must be greater than 0."*, *"GLB export is
deferred: no reliable local exporter is available in this environment."*

Three path-traversal attempts (in a project id, in a download path, and an
absolute Windows path as an id) were all refused with 404 and leaked no file
content.

### Fresh environment and backup (Phases 14 and 15)

27/27 checks passed. On a brand-new install all four stores initialise with a
usable schema, and project creation, engineering, export, assembly and the
evaluation corpus all work.

The backup archive contained exactly the four databases, the capability
registry, MCP config and local config — 7 entries, 1.0 KB. It **excluded**
`.env`, `node_modules`, `.venv311`, `runtime/logs`, log files and bulk
generated outputs, and the planted API key string appeared nowhere in the
archive bytes.

### Startup, ports and process cleanup (Phases 16, 17, 18)

- `doctor` reports READY WITH WARNINGS and exits 0 with no API key configured.
- Production mode starts and serves app plus API from one origin.
- **Port conflict:** starting on a port held by an unrelated process printed the
  actionable message and exited 1. The unrelated process was still running
  afterwards. The launcher never terminates a process it did not start.
- **Cleanup:** after `stop`, the tracked backend was gone, the port was freed,
  no orphan remained, and two unrelated long-running servers on 8000 and 5173
  were untouched.
- Runs without `OPENAI_API_KEY`: the app starts and reports `AI NOT CONFIGURED`,
  and every deterministic feature works.

### Automated gate (Phases 5, 6, 7 of the release checklist)

`python scripts/release_check.py` — **13/13 stages passed**:

| Stage | Result |
| --- | --- |
| Ruff | pass |
| GitHub Actions lint | pass |
| Deployment CLI | pass |
| Python tests | **312 passed** |
| Evaluation smoke | 28 cases |
| Full benchmark | **93 cases** |
| Regression compare | **0 regressions** |
| Frontend typecheck | pass |
| Frontend tests | **71 passed** |
| Frontend build | pass |
| Security scan | pass |
| Deployment safety | pass |
| Documentation links | pass |

Benchmark detail: 93 cases — 85 pass, 0 fail, 4 cleanly unsupported, 4 correctly
ambiguous, **0 regressions**. The baseline was not touched.

`npm audit`: **0 vulnerabilities.**

Bundle, unchanged from RC1: initial JS 303.29 kB (gzip 91.24), lazy `three`
477.56 kB, lazy `CadViewer` 37.17 kB, CSS 24.86 kB. No build warning.

### Keyboard and accessibility (Phases 21 and 22)

Code-level audit only; see Visual Review for what this does not cover.

All 75 button elements in the shipped source carry an accessible name (visible
text, `aria-label`, or `title`). An initial scan flagged one, which turned out
to be a false positive in the scan itself — the name is a dynamic
`{confirmDialog.confirmLabel}` expression that the regex stripped.

Present in the source: 23 `aria-label`, 4 `role="dialog"` with 3 `aria-modal`,
3 `autoFocus` for initial dialog focus, 7 `aria-pressed` on toggles, 2
`aria-expanded`, `role="alert"` on the error panel, 3 `role="status"`, 1
`aria-live` region, a global `:focus-visible` indicator, and a
`prefers-reduced-motion` block.

Shortcut-guard logic is covered by the frontend test suite: every bare-key
binding (`F`, `0`–`3`, `?`) is marked `blockedWhileTyping`, `Ctrl+K` and `Esc`
are not, and `isTextEntryTarget` recognises `input`, `textarea`, `select` and
`contenteditable`.

### Layout arithmetic at the narrowest target

Not a substitute for a visual check, but a checkable fact: the workspace grid is
`292px minmax(520px, 1fr) 340px` with two 1px gaps, so its minimum width is
**1154px**, below the 1180px body minimum. At 1366px the centre column receives
734px, comfortably above its 520px minimum, so there is **no horizontal overflow
at 1366×768**. Vertically, 768 − 78 header − 208 bottom row − 1 gap leaves 481px
for the viewer row.

## Visual Review - PERFORMED (rc.1)

The maintainer carried out the manual review that this environment could not,
and it found what the automated gates structurally could not: the product
worked, but the workspace did not read as one.

### Finding: CAD workspace too crowded to navigate - HIGH

Observed in rc.1:

- Too much information visible simultaneously.
- The project browser held a permanent full-height left column while editing.
- Revision history held a permanent horizontal band of roughly 20-25% of the
  screen.
- The assembly inspector was extremely dense.
- **The design assistant was pushed below the visible fold**, in a 340x208 px
  cell in the bottom-right corner. The user had to scroll to reach the primary
  input.
- A browser-level vertical scrollbar existed in the main workspace.
- The interface read as a developer or debug workspace rather than a CAD
  product; there was no obvious place to start.

Root causes, both confirmed in the stylesheet:

1. `body` and `.workspace` used `min-height: 100vh` rather than a fixed height,
   so content could push the document past the viewport. That is what produced
   the page scrollbar.
2. The grid was `292px | centre | 340px` over rows `1fr | 208px`, with the
   design tree spanning both rows. The prompt therefore landed in the
   bottom-right cell, the smallest region on screen, for the most important
   interaction in the product.

Severity **HIGH**: no data is at risk and no geometry is wrong, but the primary
workflow was not discoverable, which is a release-quality problem for a v1.0.

### Fix: rc.2 workspace simplification

| Area | rc.1 | rc.2 |
| --- | --- | --- |
| Shell | `min-height: 100vh`, page scrolls | `height: 100vh`, `overflow: hidden`; three-row grid |
| Prompt | bottom-right 340x208 cell, below the fold | dedicated shell row, always visible |
| Project browser | permanent full-height column | drawer behind **Open** |
| Revision history | permanent horizontal band | drawer behind **History** |
| Inspector | every subsystem stacked | tabs, filtered by mode |
| Learning / Evaluation / Capabilities / System | in the editing inspector | **Tools** drawer |
| Export | header buttons plus a full inspector panel | **Export** drawer |
| Assembly component | source, XYZ, rotation, bbox, 8 micro buttons | name, 2 toggles, labelled fields, Apply |
| Header | 78 px technical strip | 52 px: identity, context, status, 5 entries |
| Detail level | everything, always | Simple by default, Advanced on request |
| Status lines | permanent boxes | floating toasts |

Scrolling is now internal to each rail, drawer and the prompt bar. Either side
rail collapses to hand its width to the viewer.

### Measured outcome

Computed from the shipped CSS track sizes, and confirmed against the served
bundle (41 of 42 shell assertions passed on the first run; the one miss was the
check itself looking in the main bundle for toolbar labels that live in the
lazy-loaded viewer chunk, verified separately):

| Resolution | Work area height | Viewer share of width |
| --- | --- | --- |
| 1920x1080 | 978 px | 71% |
| 1440x900 | 798 px | 61% |
| 1366x768 | 666 px | 59% |

Header 52 px plus prompt 50 px is a fixed 102 px of vertical chrome, so at the
narrowest target 666 px remains for the tree, viewer and inspector, none of
which can push the page taller than the viewport.

### AI not configured

`OPENAI_API_KEY` is not set in this environment, and the review screenshot
showed `AI ASSISTANT NOT CONFIGURED`. That is not hidden. In rc.2 the prompt box
stays usable but **SEND is disabled**, the notice names the variable, and a
Setup help action opens system information. A user can no longer send a request
that cannot work and then receive a generic parser failure.

**Manual AI prompt test: NOT TESTED - OPENAI_API_KEY NOT CONFIGURED.** The
suggested prompt was not run against a live provider. The equivalent
deterministic path was exercised instead: the same 100 x 60 x 5 mm plate with
four corner holes was generated through `POST /api/generate` with a structured
spec, and project load, history, preview, STEP download and revision restore all
returned 200.

## Visual Review - rc.2 NOT YET PERFORMED

The redesign has not itself been through a browser-based review. No browser
automation is available here (no Playwright, Puppeteer, Selenium, chromedriver
or browser binary), and installing one would change the dependency set during a
release-validation pass.

What is verified for rc.2: the new markup and CSS are present in the served
bundle, the layout arithmetic above, the full workflow over the API, and 101
frontend tests covering prompt gating, Enter versus Shift+Enter, tab filtering
and drawer exclusivity.

What a reviewer should confirm at 1920x1080, 1440x900 and 1366x768:

- no browser-level scrollbar during ordinary editing
- header, viewer, prompt input, design tree and inspector all visible at once
- drawers open over the workspace without shifting it
- collapsing each rail enlarges the viewer
- the disabled SEND state and its notice read clearly
- tab switching in the inspector, and Simple versus Advanced
- the assembly component card at a realistic component count

## Issues

| Issue | Severity | Reproducible | Fixed | Release blocking |
| --- | ---: | ---: | ---: | ---: |
| **CAD workspace too crowded; prompt input below the fold; page-level scrollbar** | **HIGH** | Yes | **Yes (rc.2)** | Was blocking; resolved |
| rc.2 redesign not yet visually reviewed | - (evidence gap, not a defect) | n/a | No | **Gates promotion** |
| `docs/release-candidate.md` claimed 273 Python and 73 frontend tests; actual counts are 312 and 71 | MEDIUM (misleading docs) | Yes | **Yes** | No |
| `unknown part type` surfaces a raw pydantic `union_tag_invalid` string with a `422:` prefix embedded in the message | LOW | Yes | No | No |
| No LICENSE configured | — (documented) | n/a | No | No |

The automated and functional passes found nothing of BLOCKER or HIGH severity.
The manual visual review found one HIGH usability defect, which was fixed in
rc.2. One MEDIUM documentation inaccuracy was also found and corrected.

### The documentation inaccuracy

`docs/release-candidate.md` carried test counts from an earlier milestone: 273
Python tests (the v0.19 figure) and 73 frontend tests (the count before the
export-availability helpers were folded into `ExportPanel`). The real figures
are 312 and 71, both re-verified by running the suites. Corrected in this pass.
Published release documentation overstating its own test coverage is exactly the
kind of thing a validation pass exists to catch, which is why it is logged as
MEDIUM rather than cosmetic.

### Notes on the two non-blocking items

**Raw pydantic message.** Hand-posting `{"part_type": "flux_capacitor"}` returns
a structured 422 whose detail is pydantic's union-discriminator error, with the
status code redundantly prefixed into the string. It is not reachable from the
UI, where part types come from the schema. The frontend maps unrecognised
categories to a clean *"SOMETHING WENT WRONG"* title and keeps the raw text
behind *Show details*, so a user never sees it unprompted. Cosmetic; left alone
rather than touched during validation.

**License.** There is still no `LICENSE` file. One was not created, per
instruction. This is stated in `CHANGELOG.md`, `docs/release-candidate.md` and
the README limitations.

## Decision

**RC2 PRODUCED - READY FOR v1.0.0 AFTER DOCUMENTED MANUAL VISUAL CHECK OF RC2**

Every functional, deterministic and safety gate passes, on evidence rather than
assumption: 90/90 real-world design checks, 50/50 workflow checks, 83/83
export/lifecycle/capability/learning checks, 37/37 API checks, 27/27 fresh
environment and backup checks, and 13/13 automated release stages with 0
benchmark regressions.

The manual visual review of rc.1 found a HIGH usability defect, which is fixed
in rc.2. Because the visible product experience changed materially, another
validation cycle is appropriate rather than promoting straight to v1.0.0.

All gates were re-run against the redesign: 312 Python tests, 101 frontend tests
(up from 71), 93 benchmark cases with 0 regressions, 13/13 release stages, npm
audit clean. The outstanding item is a browser-based review of rc.2 itself.
