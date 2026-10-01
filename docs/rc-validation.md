# Release Candidate Validation

## Summary

| Field | Value |
| --- | --- |
| Validation date | 2026-10-01 |
| Starting commit | `6e4a7e3` |
| Starting tag | `v1.0.0-rc.1` |
| Version under test | 1.0.0-rc.1 |
| Code changes required | **none** |
| Release blockers | **none** |
| Decision | **READY FOR v1.0.0 AFTER DOCUMENTED MANUAL VISUAL CHECK** |

RC1 was tagged without a validation pass having been run; this document is that
pass. No defect found during it required a code change, so **no rc.2 was
produced** and `v1.0.0-rc.1` remains the candidate.

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

## Visual Review — NOT PERFORMED

This was the one area RC1 flagged as unverified, and **it remains unverified.**

No browser automation is available in this environment: no Playwright,
Puppeteer, Selenium, chromedriver, Chrome or Edge binary, and no such package in
`web/node_modules`. Installing Playwright would pull browser binaries and change
the dependency set during a release-validation pass, which is out of scope.

Reading CSS and counting ARIA attributes is not a visual check. The following
have therefore **not** been verified at 1920×1080, 1440×900 or 1366×768:

- vertical clipping or text truncation inside panels
- real tab order and focus-ring visibility on screen
- modal positioning and backdrop behaviour
- panel collisions, overflow or scrollbar behaviour in practice
- legibility of small labels, and spacing consistency as seen
- the 3D viewer rendering, selection highlight and hover behaviour
- empty, loading and error states as they actually appear

### What a reviewer should do

Start the app and walk the list above at the three widths:

```powershell
.\scripts\start.ps1
```

Then open `http://127.0.0.1:8000` and check: landing page, project browser,
part workspace, assembly workspace, design tree, inspector, viewer toolbar,
prompt console, revision history, export panel, evaluation panel, system/about
dialog, confirmation and rename dialogs, empty states, an error state, and a
loading state.

Record the outcome in this file, then promotion to v1.0.0 can proceed.

## Issues

| Issue | Severity | Reproducible | Fixed | Release blocking |
| --- | ---: | ---: | ---: | ---: |
| Visual review not performed (no browser tooling available) | — (evidence gap, not a defect) | n/a | No | **Gates promotion** |
| `docs/release-candidate.md` claimed 273 Python and 73 frontend tests; actual counts are 312 and 71 | MEDIUM (misleading docs) | Yes | **Yes** | No |
| `unknown part type` surfaces a raw pydantic `union_tag_invalid` string with a `422:` prefix embedded in the message | LOW | Yes | No | No |
| No LICENSE configured | — (documented) | n/a | No | No |

Nothing of BLOCKER or HIGH severity was found. One MEDIUM documentation
inaccuracy was found and corrected; it was documentation only and required no
code change, so RC1 stands as the candidate.

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

**READY FOR v1.0.0 AFTER DOCUMENTED MANUAL VISUAL CHECK**

Every functional, deterministic and safety gate passes, on evidence rather than
assumption: 90/90 real-world design checks, 50/50 workflow checks, 83/83
export/lifecycle/capability/learning checks, 37/37 API checks, 27/27 fresh
environment and backup checks, and 13/13 automated release stages with 0
benchmark regressions.

The single outstanding item is the manual visual review, which cannot be done
here. Promotion should wait until a human has walked the UI at the three target
resolutions and recorded the result above.
