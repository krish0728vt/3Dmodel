# SHAH INDUSTRIES CAD Workspace

[![CI](https://github.com/krish0728vt/3Dmodel/actions/workflows/ci.yml/badge.svg)](https://github.com/krish0728vt/3Dmodel/actions/workflows/ci.yml)

AI-assisted mechanical design workspace for safe prompt-to-STEP generation, revisioned CAD projects, parametric design intent, engineering checks, capability-gated extensions, and lightweight assemblies.

The application is intentionally conservative: AI can propose structured CAD intent, but geometry is produced through typed schemas, Pydantic validation, deterministic Python/CadQuery execution, revision history, and explicit capability gates.

## Status

Current architecture:

```text
SHAH INDUSTRIES
  |
  +-- SHAH Design Assistant
  |     +-- prompt parsing
  |     +-- structured design intent
  |     +-- safe edit requests
  |
  +-- 3D CAD Workspace
        +-- template engine
        +-- operation engine
        +-- parametric resolver
        +-- engineering core
        +-- assembly foundation
        +-- revision core
        +-- learning core
        +-- capability core
        +-- STEP / STL / preview exports
```

Implemented:

- Template parts: mounting plates, boxes, cylinders, spacers, L-brackets, and electronics enclosures.
- Operation plans: sketches, extrudes, cuts, holes, fillets, chamfers, shells, lofts, sweeps, patterns, booleans, bosses, ribs, and external capability operations.
- Project store with immutable revisions, undo, redo, restore, diffs, STEP export, and STL export.
- Project workflow with search, sorting, recent-open tracking, rename, duplicate, archive, unarchive, and confirmed delete.
- Semantic preview data for the web viewer.
- Engineering analysis with bounding boxes, volume, surface area, center of mass, materials, mass estimates, units, and manufacturability warnings.
- Design intent parameters and relationships resolved before CAD generation.
- Learning Core with normalized failures, lessons, successful patterns, repair evidence, and capability performance metrics.
- Capability Core with discovery, self-test, approval, enablement, checksums, and schema-validated invocation.
- Assembly Foundation with assembly records, revisions, transforms, visibility, grounding, coarse bounding-box interference checks, engineering rollups, manifest export, and API/web controls.
- React workspace using the supplied SHAH INDUSTRIES logo asset from `web/public`.

## Documentation Map

Detailed notes live in focused docs:

- [Architecture](docs/architecture.md)
- [API](docs/api.md)
- [Assemblies](docs/assemblies.md)
- [Exporting](docs/exporting.md)
- [Evaluation](docs/evaluation.md)
- [Projects](docs/projects.md)
- [Parametrics](docs/parametrics.md)
- [Learning Core](docs/learning-core.md)
- [Capabilities](docs/capabilities.md)
- [Development](docs/development.md)
- [Workflows And Recipes](docs/workflows.md)

## Repository Layout

```text
ai/             Prompt parsing and structured schemas
api/            FastAPI app, dependencies, routes, and request schemas
assemblies/     Assembly store, revisions, transforms, preview, export, engineering
cad/            CadQuery generation, operations, validation, preview, exports
capabilities/   Capability registry, manifests, adapters, invocation gate
config/         Optional runtime configuration
data/           SQLite databases and capability registry files
docs/           Focused project documentation
engineering/    Geometry metrics, materials, units, manufacturability warnings
learning/       Failure memory, lessons, patterns, repairs, analytics
parametrics/    Design parameters, relationships, resolver, migration
plans/          Example structured CAD plans
projects/       Project/revision store, editor, diffs, serialization
scripts/        Utility scripts, including logo conversion
tests/          Backend tests
web/            React/Vite CAD workspace
```

## Quick Start

Use Python 3.11 on Windows.

```powershell
.\.venv311\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the API:

```powershell
.\.venv311\Scripts\python -m uvicorn api.server:app --reload
```

Run the web workspace:

```powershell
cd web
npm.cmd install
npm.cmd run dev
```

Open the Vite URL shown in the terminal, usually:

```text
http://localhost:5173
```

## Testing

Backend:

```powershell
.\.venv311\Scripts\python -m pytest
```

Frontend typecheck:

```powershell
cd web
npm.cmd test
```

Production build:

```powershell
cd web
npm.cmd run build
```

Evaluation smoke benchmark:

```powershell
.\.venv311\Scripts\python app.py evaluate smoke
```

Full local development check:

```powershell
.\.venv311\Scripts\python scripts/check_all.py
```

See [Development](docs/development.md) for CI, dependency, security-scan, and commit workflow details.

## Running From The CLI

Generate a model:

```powershell
.\.venv311\Scripts\python app.py "Create a 120 by 80 by 6 mm mounting plate with four 5 mm holes"
```

Project history:

```powershell
.\.venv311\Scripts\python app.py project list
.\.venv311\Scripts\python app.py project history <project_id>
.\.venv311\Scripts\python app.py project diff <project_id> 1 2
.\.venv311\Scripts\python app.py project restore <project_id> 1
.\.venv311\Scripts\python app.py project export <project_id>
.\.venv311\Scripts\python app.py project rename <project_id> "New name"
.\.venv311\Scripts\python app.py project duplicate <project_id>
.\.venv311\Scripts\python app.py project archive <project_id>
.\.venv311\Scripts\python app.py project unarchive <project_id>
```

Learning:

```powershell
.\.venv311\Scripts\python app.py learning stats
.\.venv311\Scripts\python app.py learning failures
.\.venv311\Scripts\python app.py learning lessons
.\.venv311\Scripts\python app.py learning patterns
.\.venv311\Scripts\python app.py learning revalidate
```

Capabilities:

```powershell
.\.venv311\Scripts\python app.py capabilities sources
.\.venv311\Scripts\python app.py capabilities discover
.\.venv311\Scripts\python app.py capabilities test local.spur_gear_generator
.\.venv311\Scripts\python app.py capabilities approve local.spur_gear_generator
.\.venv311\Scripts\python app.py capabilities enable local.spur_gear_generator
```

## Web Workspace

The web app has five working regions:

- Header: backend status, refresh, STEP/STL download links, and compact SHAH INDUSTRIES logo.
- Design tree: searchable project browser, lifecycle actions, operation tree, parameters, and relationships.
- Viewer: STL rendering, semantic object selection, camera tools, measurements, and bounding-box readouts.
- Inspector: selection details, structured edits, design intent, assembly controls, engineering, learning, and capabilities.
- Prompt console: create and edit models conversationally.
- Evaluation panel: read-only summary of the latest deterministic benchmark report.

The empty workspace uses the larger SHAH INDUSTRIES logo and example prompts.

Shortcut help is available with `?`. The main workflow shortcuts are `Ctrl+K` for the prompt, `Ctrl+Z` for undo, `Ctrl+Shift+Z` for redo, and `Esc` to close overlays or clear selection.

## Core Data Flow

Generation:

```text
prompt
  -> parser
  -> Pydantic CAD schema
  -> design-intent resolver
  -> operation/template validator
  -> CadQuery generator
  -> geometry validation
  -> project revision
  -> STEP/STL/preview
```

Editing:

```text
project revision
  -> typed edit request
  -> new model candidate
  -> validation/generation
  -> immutable child revision
```

Assembly:

```text
project revisions or local files
  -> assembly components
  -> component transforms
  -> assembly revision
  -> preview / engineering / manifest
```

## Supported Template Parts

Mounting plate:

- width, height, thickness, corner radius
- hole list
- optional design parameters and relationships

Box:

- width, depth, height
- optional vertical corner radius

Cylinder:

- diameter and height
- optional center hole

Spacer:

- outer diameter, inner diameter, height

L-bracket:

- width, height, leg depth, thickness
- optional corner radius

Electronics enclosure:

- internal width/depth/height
- wall and bottom thickness
- corner radius
- mounting posts
- optional design parameters and relationships

## Supported Operation Plans

Operation plans are explicit ordered CAD programs. Supported operation families:

- Primitive creation: box, cylinder
- Sketch creation: structured sketch, rectangle, circle
- Solid creation: extrude, revolve, loft, sweep
- Removal: cut extrude, through hole, blind hole, counterbore, countersink, generic cut hole
- Additive features: boss, rib
- Finishing: fillet, chamfer, shell
- Patterns and transforms: rectangular hole pattern, circular hole pattern, linear pattern, circular pattern, mirror
- Booleans: union and cut
- External capability invocation through the gated Capability Core

The operation engine rejects duplicate IDs, invalid references, forward references, unsupported selectors, invalid dimensions, and unsafe capability use.

## Design Intent

Design intent is represented by:

- driving parameters that users can edit
- derived parameters calculated by safe expression nodes
- geometric relationships such as centered, aligned, symmetric, equal spacing, relative position, and edge offsets

No free-form expression evaluation is used. Expressions are typed nodes such as `literal`, `parameter_ref`, `add`, `subtract`, `multiply`, `divide`, `min`, and `max`.

See [Parametrics](docs/parametrics.md).

## Assembly Foundation

Assemblies store ordered component lists as immutable revisions. Components may reference:

- project revisions
- generated files
- capability outputs
- imported local STEP/STL files

Each component has:

- source metadata
- transform in millimeters/degrees
- visibility state
- grounded state
- optional metadata

The current milestone performs deterministic transform management, preview bounding boxes, manifest export, known-mass aggregation, center-of-mass rollup when possible, and coarse interference detection using world-space bounding boxes.

See [Assemblies](docs/assemblies.md).

## Export And Interoperability

STEP remains the primary engineering export. The export layer supports revision-aware STEP, STL quality presets, structured-sketch DXF, export manifests, SHA-256 checksums, ZIP packages, project export history, assembly manifest export, and transformed assembly STEP/STL where the CAD kernel supports the solids.

GLB and OBJ are intentionally deferred until a reliable local exporter is available. See [Exporting](docs/exporting.md).

## API Highlights

Start the API:

```powershell
.\.venv311\Scripts\python -m uvicorn api.server:app --reload
```

Important routes:

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Backend status |
| `POST` | `/api/generate` | Generate and optionally save a project |
| `GET` | `/api/projects` | List projects |
| `GET` | `/api/projects/{id}` | Project detail and current model |
| `POST` | `/api/projects/{id}/duplicate` | Duplicate a project revision |
| `POST` | `/api/projects/{id}/archive` | Archive a project |
| `POST` | `/api/projects/{id}/unarchive` | Restore an archived project |
| `DELETE` | `/api/projects/{id}` | Delete a confirmed project |
| `POST` | `/api/projects/{id}/edit` | Apply a typed or parsed edit |
| `POST` | `/api/projects/{id}/parameters/{parameter_id}` | Update a driving design parameter |
| `GET` | `/api/projects/{id}/resolved-design` | Resolve design intent |
| `GET` | `/api/projects/{id}/download/step` | Download STEP |
| `GET` | `/api/projects/{id}/download/stl` | Download STL |
| `GET` | `/api/projects/{id}/engineering` | Engineering report |
| `GET` | `/api/projects/{id}/revisions/{rev}/preview` | Semantic preview metadata |
| `GET` | `/api/assemblies` | List assemblies |
| `POST` | `/api/assemblies` | Create assembly |
| `POST` | `/api/assemblies/{id}/edit` | Apply assembly edit |
| `GET` | `/api/assemblies/{id}/preview` | Assembly preview metadata |
| `GET` | `/api/assemblies/{id}/engineering` | Assembly engineering summary |
| `GET` | `/api/assemblies/{id}/download` | Assembly manifest |
| `POST` | `/api/exports` | Batch export project or assembly revisions |
| `GET` | `/api/exports/{export_id}/download` | Download recorded export |
| `POST` | `/api/parametrics/validate` | Validate and resolve parametric design |
| `GET` | `/api/learning/stats` | Learning Core stats |
| `GET` | `/api/capabilities` | Capability registry records |

See [API](docs/api.md).

## Persistence

Default local data:

- `data/shah_projects.db`: projects, revisions, material assignments
- `data/shah_learning.db`: failures, lessons, patterns, repairs, analytics
- `data/shah_assemblies.db`: assemblies and assembly revisions
- `data/capabilities.json`: discovered capability records
- `outputs/`: generated STEP/STL files, previews, and assembly manifests

All revision records are append-only. Undo, redo, and restore change the active pointer instead of mutating prior revisions.

## Security Boundary

The project keeps AI and external integrations inside explicit boundaries:

- Pydantic schemas define the accepted design language.
- CadQuery generation is deterministic local code.
- Capabilities require discovery, self-test, approval, enablement, and schema validation.
- Learning records are advisory and cannot execute code.
- Frontend code does not contain secrets.
- No arbitrary model-generated Python, JavaScript, package installation, shell commands, or remote code execution is permitted.
- External capability metadata cannot silently grant trust or run commands.

## Known Limitations

- Assembly interference detection is currently coarse and based on transformed bounding boxes, not precise BREP collision.
- Combined assembly STEP/STL export is early and best suited for simple visible solid components.
- Imported STL components can be tracked and previewed as sources, but precise engineering metrics depend on loadable CAD geometry.
- Natural-language assembly editing is intentionally limited to simple deterministic commands.
- Parametric relationships cover common design intent but are not a full constraint solver.
- Viewer selection maps semantic operation outputs, not every low-level CAD face or edge.
- The AI parser supports bounded prompt-to-spec generation and may need explicit structured edits for complex designs.

## Development Guidelines

- Prefer typed schema changes over stringly typed parsing.
- Keep generated geometry deterministic.
- Add tests for every new operation family, relationship, capability, API route, and revision behavior.
- Keep user data local unless an explicitly approved capability is invoked.
- Do not commit generated build artifacts unless they are intentional examples or static assets.
- Do not store secrets in source files, logs, learning records, or frontend bundles.

## Example Workflows

Worked prompt-to-STEP examples, parametric and assembly edit walkthroughs, and the
recipes for adding a template part, an operation, or an assembly feature live in
[Workflows And Extension Recipes](docs/workflows.md).

## Manual Verification Checklist

Before handing off a milestone:

- Run the backend tests.
- Run the frontend typecheck.
- Run the production web build.
- Confirm security scans are clean or explain expected policy-only matches.
- Verify README line count moved in the intended direction.
- Check `git status --short`.
- Do not commit or push unless explicitly asked.

## Branding

The web app uses the SHAH INDUSTRIES logo from `web/public`. The intended usage is:

- compact logo in the application header
- larger logo in the empty workspace
- no repeated decorative logo wallpaper

If the PNG source changes, regenerate the WebP fallback from that source. Do not redesign or trace a new logo unless explicitly requested.

## Ownership

This repository is for SHAH INDUSTRIES CAD workspace development. Generated CAD files remain local project outputs unless the user explicitly exports or shares them.
