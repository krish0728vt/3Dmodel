# Architecture

SHAH INDUSTRIES is structured as a deterministic CAD pipeline with AI-assisted intent at the edges.

## Main Layers

- `ai/`: prompt parsing and typed schema definitions.
- `parametrics/`: driving parameters, relationships, dependency resolution, and schema migration.
- `cad/`: template and operation-plan generation through CadQuery.
- `projects/`: immutable project revisions, edits, diffs, export helpers, and material assignments.
- `assemblies/`: assembly records, revisions, transforms, preview, engineering, and manifest export.
- `engineering/`: physical metrics, materials, units, and manufacturability checks.
- `learning/`: normalized failures, lessons, successful patterns, repair evidence, and analytics.
- `capabilities/`: discovery, approval, enablement, and gated external operation invocation.
- `api/`: FastAPI route layer over the same local services.
- `web/`: React/Vite workspace for project editing, viewing, learning, capabilities, engineering, and assemblies.

## Data Flow

Prompt generation:

```text
prompt -> parser -> schema -> parametric resolver -> validation -> CadQuery -> revision -> exports
```

Project editing:

```text
current revision -> typed edit -> model candidate -> validation -> new immutable revision
```

Assembly editing:

```text
current assembly revision -> typed edit -> validated component list -> new immutable assembly revision
```

## Design Principles

- Use typed Pydantic models for anything generated or edited.
- Keep the CAD kernel isolated behind allowlisted operations.
- Treat every saved revision as immutable history.
- Make AI output advisory until it passes schema, validation, and geometry checks.
- Keep capabilities opt-in, reviewed, and reversible.
- Keep Learning Core advisory; it can rank context, not bypass safety.
