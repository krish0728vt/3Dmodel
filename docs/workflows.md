# Workflows And Extension Recipes

Worked end-to-end examples and the steps for adding new templates, operations,
and assembly features. See [Development](development.md) for setup, checks, and CI.

## Example Workflows

### Mounting Plate

Prompt:

```text
Create a 120 by 80 by 6 mm mounting plate with four 5 mm holes near the corners.
```

Expected path:

- parser returns a mounting plate spec
- generator produces a plate with through holes
- project store saves revision 1
- web viewer displays STL preview
- STEP/STL exports become available

### Electronics Enclosure

Prompt:

```text
Create an open electronics enclosure with 80 mm internal width, 50 mm depth, 25 mm height, 2.5 mm walls, and four mounting posts.
```

Expected path:

- parser returns an electronics enclosure spec
- generator creates an open-top box and posts
- engineering panel can estimate mass after material assignment
- manufacturability warnings highlight thin walls or process concerns

### Operation Plan

Operation plans are useful when the design needs explicit build steps:

```json
{
  "schema_version": "1.2",
  "project_name": "pocket_plate",
  "operations": [
    {
      "id": "base",
      "operation_type": "create_box",
      "width_mm": 80,
      "depth_mm": 50,
      "height_mm": 8
    },
    {
      "id": "pocket_profile",
      "operation_type": "create_sketch",
      "sketch": {
        "id": "pocket_profile",
        "plane": "XY",
        "origin": [0, 0, 4.1],
        "closed": true,
        "entities": [
          {
            "entity_type": "rectangle",
            "width_mm": 40,
            "height_mm": 20
          }
        ]
      }
    },
    {
      "id": "pocket",
      "operation_type": "cut_extrude",
      "target_id": "base",
      "sketch_id": "pocket_profile",
      "distance_mm": 3
    }
  ],
  "final_object_id": "pocket"
}
```

### Parametric Edit

For parametric models, a driving parameter update follows this path:

```text
parameter value -> resolver -> validation -> new project revision -> preview/export refresh
```

The previous revision remains intact.

### Assembly Edit

Typical assembly sequence:

```text
create project A
create project B
create assembly from A
add B as component
move B by 20 mm on X
ground A
hide/show B as needed
download manifest
```

Each move, visibility change, and grounding change creates a new assembly revision.

## Adding A Template Part

1. Add a Pydantic model to `ai/schemas.py`.
2. Add parser mapping only if prompt parsing should support it.
3. Add CadQuery generation in `cad/generator.py`.
4. Add validation if dimensions need special rules.
5. Add preview metadata if the part should expose semantic selection.
6. Add tests for generation, validation, API behavior, and export.
7. Update docs with supported fields and known limitations.

## Adding An Operation

1. Add the operation schema to `ai/schemas.py`.
2. Add validation in `cad/operation_validator.py`.
3. Add execution in `cad/operation_executor.py`.
4. Add preview support in `cad/preview.py`.
5. Add editor support if structured edits can target it.
6. Add tests for success, invalid references, and failure classification.

## Adding An Assembly Feature

1. Add or extend a typed edit in `assemblies/models.py`.
2. Apply the edit in `assemblies/manager.py`.
3. Validate references and transforms in `assemblies/validation.py`.
4. Return API-safe data through `api/routes/assemblies.py`.
5. Add frontend controls only after the route behavior is covered by tests.
6. Update [Assemblies](assemblies.md).
