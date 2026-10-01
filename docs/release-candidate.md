# v1.0.0-rc.1 Release Candidate

Written for someone evaluating whether this is fit to use, not for someone who
followed its development.

## What SHAH INDUSTRIES does

A local, single-user CAD workspace for mechanical parts. You describe a part in
plain language or enter dimensions directly; the request becomes a typed,
validated specification, and geometry is produced by a deterministic
Python/CadQuery pipeline. Nothing the AI returns is executed as code -- it can
only fill in a schema the application already understands.

Core capabilities:

| Area | What you get |
| --- | --- |
| Generation | Template parts (plate, box, cylinder, spacer, bracket, enclosure) and multi-step operation plans |
| Operations | Boxes, cylinders, sketches, extrude, pockets, through/blind/counterbore/countersink holes, bosses, ribs, patterns, booleans, fillets, chamfers, shells, lofts, sweeps, mirrors |
| Design intent | Named parameters with driving and derived roles, edge offsets, centering, and dependent dimensions that survive a resize |
| Projects | Revision history with diffs, undo and redo, duplicate, archive, search |
| Engineering | Mass and centre of mass from a material catalogue, plus manufacturability checks for 3D printing and CNC |
| Assemblies | Multiple components with explicit transforms, grounding, visibility, interference reporting, and aggregate mass |
| Exports | STEP, STL (draft and high), DXF for structured sketches, ZIP packages with a manifest and SHA-256 checksums |
| Capabilities | Opt-in external generators, gated behind explicit discovery, approval, and enablement |
| Learning Core | Records failure categories and repair outcomes to improve planning over time |
| Evaluation | A 93-case deterministic benchmark with baseline regression comparison |

## What is tested

All verification is deterministic and runs offline. No API key, no network, no
MCP server, no browser.

| Suite | Scope |
| --- | --- |
| Python tests | 273 tests across parsing, schemas, geometry, validation, projects, revisions, parametrics, engineering, assemblies, exports, capabilities, learning, the API, and local deployment |
| Frontend tests | 73 Vitest tests over the pure presentation logic: prompt lifecycle, error mapping, loading and empty states, mode, interference wording, export availability, shortcuts, formatting, unit conversion |
| Benchmark | 93 cases over 18 categories; a 28-case smoke subset runs in about 18 seconds |
| Regression gate | Every benchmark case is compared against a committed baseline; a pass becoming a failure fails the build |
| CI | Python tests, frontend tests and build, evaluation smoke, and security checks on every push and pull request |

Run everything with:

```powershell
python scripts/release_check.py
```

## Benchmark coverage

93 cases: 85 pass, 0 fail, 4 cleanly unsupported, 4 correctly treated as
ambiguous.

Categories: basic primitives, holes, mounting parts, brackets, enclosures,
boolean operations, patterns, sketches, shells, lofts, sweeps, parametrics,
conversational edits, engineering analysis, assemblies, capabilities, exports,
invalid inputs, ambiguous inputs.

The corpus deliberately includes failures that must stay clean: fillets larger
than the available edge, shells thicker than the body, holes larger than the
plate, bores exceeding the outer diameter, references to features that do not
exist, duplicate operation identifiers, and unusable assembly components. Each
must produce an explained refusal rather than a crash or silent success.

## Intentionally unsupported

These are decisions, not gaps waiting on a bug fix:

- **FEA and CFD.** Out of scope.
- **A geometric constraint solver.** Design intent is expressed as parameters
  and relationships, not solved constraints.
- **Mate-based assembly.** Components are placed with explicit transforms.
- **Native BREP face and edge selection.** Selection is semantic, at the
  operation level.
- **GLB and OBJ export.** No reliable local exporter, so they are shown as
  unsupported rather than offered.
- **Real threaded fasteners, sheet-metal unfolding, gear trains as a part type.**
  Refused cleanly; a capability can supply specific generators.
- **Authentication and multi-user.** The app is local and single-user.
- **Docker.** Deferred; see [deployment.md](deployment.md).

## Known limitations

- Measurements in the viewer are taken against the preview mesh, so they are
  approximate rather than exact BREP distances.
- Interference is a bounding-box check unless a precise test is available; the
  UI says which was used and never presents a coarse overlap as a collision.
- Backup is automated; restore is manual, on purpose, rather than shipping an
  automated overwrite of live databases.
- Natural-language quality depends on the configured provider and model. Nothing
  in the tested behavior depends on it.
- The lazy-loaded Three.js chunk is about 478 kB. It is not part of the initial
  download, and it cannot be split further in any useful way.
- Desktop layouts only, down to 1366x768. Phone widths are not a target.
- No license is currently configured for this repository.

## Recommended environment

| Component | Recommendation |
| --- | --- |
| OS | Windows 10 or 11. The Python layer is cross-platform; the PowerShell entry points are Windows. |
| Python | 3.11 exactly. The CadQuery/OpenCascade wheels are built per minor version. |
| Node.js | Current LTS, 20 or newer. |
| Display | 1440x900 or larger. |
| Disk | A few hundred MB for dependencies, plus project geometry. |
| Network | Only for installation, and for natural-language prompts if you enable them. |

Setup:

```powershell
git clone https://github.com/krish0728vt/3Dmodel.git
cd 3Dmodel
.\scripts\setup.ps1
.\scripts\start.ps1
```

An `OPENAI_API_KEY` is optional. Without one, the app starts and reports
`AI NOT CONFIGURED`; every deterministic feature above still works.

## Security posture

- No `eval`, no `exec`, no `shell=True`, and no execution of model-generated
  code. The AI fills a typed schema; geometry comes from Python the project
  ships.
- Secrets live only in `.env`. No key is sent to the frontend, included in a
  backup, or echoed in a diagnostic.
- Export and download paths are resolved inside the output directory, so a
  traversal attempt cannot read elsewhere.
- The launcher never terminates a process it did not start, and never one it
  cannot still identify as its own.
- `clean` removes only regenerable artifacts; databases, exports, and projects
  are never touched.
- Capabilities are disabled until explicitly discovered, approved, and enabled.
- Binds `127.0.0.1` by default; a non-local bind prints a warning.

Enforced by `scripts/security_check.py` and `scripts/deployment_safety.py`, both
part of CI.

## After the release candidate

Candidates for v1.0 and beyond, none of which are implemented today:

- Richer assembly mates, and constraint solving beyond the current parameter and
  relationship model
- Topology-aware face and edge selection
- GLB and OBJ export if a dependable local exporter appears
- Automated restore with a safe confirmation flow
- Optional desktop packaging
- A larger benchmark corpus and more manufacturability checks
