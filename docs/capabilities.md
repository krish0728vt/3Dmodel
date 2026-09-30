# Capabilities

Capabilities are optional, explicit extensions to the core CAD engine.

A capability is metadata plus, optionally, an allowlisted local adapter or constrained HTTP endpoint. It is not arbitrary code supplied by a model.

## Lifecycle

1. Discover capability metadata.
2. Validate required fields and input schema.
3. Run self-test.
4. User approves the capability.
5. User enables the capability.
6. Operation plans may invoke it through the central gate.

Changed local manifests or adapters require re-test/review.

## Trust Levels

- `CORE`: built into the deterministic local system
- `APPROVED`: explicitly approved by the user
- `EXPERIMENTAL`: discovered but not trusted
- `DISABLED`: unavailable for generation

## Invocation Gate

The gate checks:

- capability exists
- capability is enabled
- validation passed
- input schema matches
- operation is supported
- adapter is allowlisted
- timeout and file constraints are respected

## Demo Capability

The current demo local adapter is:

```text
local.spur_gear_generator
```

Common CLI flow:

```powershell
.\.venv311\Scripts\python app.py capabilities discover
.\.venv311\Scripts\python app.py capabilities test local.spur_gear_generator
.\.venv311\Scripts\python app.py capabilities approve local.spur_gear_generator
.\.venv311\Scripts\python app.py capabilities enable local.spur_gear_generator
```

## API

- `GET /api/capabilities`
- `GET /api/capabilities/sources`
- `POST /api/capabilities/discover`
- `GET /api/capabilities/{id}`
- `POST /api/capabilities/{id}/test`
- `POST /api/capabilities/{id}/approve`
- `POST /api/capabilities/{id}/enable`
- `POST /api/capabilities/{id}/disable`
- `POST /api/capabilities/{id}/invoke`
