# Learning Core

Learning Core records what failed, what fixed it, and which patterns have evidence.

It never executes code, modifies source files by itself, approves capabilities, or bypasses validators.

## Stored Records

- failure records
- lessons
- successful patterns
- repair attempts
- repair strategies
- capability performance analytics

## Failure Categories

Categories include schema, parser, geometry, operation validation, CAD kernel, export, engineering, parametric, assembly, and capability failures.

Assembly-specific categories:

- `assembly_reference_failure`
- `assembly_transform_failure`
- `assembly_interference_failure`
- `assembly_export_failure`

Parametric-specific categories:

- `parametric_resolution_failure`
- `dependency_cycle`
- `constraint_conflict`
- `missing_design_parameter`

## Evidence Lifecycle

Lessons and patterns move through:

- `OBSERVED`
- `VALIDATED`
- `TRUSTED`
- `NEEDS_REVALIDATION`
- `DEPRECATED`

Confidence is based on evidence count, successes, failures, contradictions, and verification state.

## API

Important routes:

- `GET /api/learning/stats`
- `GET /api/learning/lessons`
- `GET /api/learning/lessons/{id}`
- `POST /api/learning/lessons/{id}/revalidate`
- `POST /api/learning/lessons/{id}/deprecate`
- `GET /api/learning/patterns`
- `GET /api/learning/patterns/{id}`
- `POST /api/learning/patterns/{id}/revalidate`
- `POST /api/learning/patterns/{id}/deprecate`
- `GET /api/learning/repair-strategies`
- `GET /api/learning/failures/analytics`
- `GET /api/learning/capabilities/analytics`
