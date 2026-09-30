# Parametrics

Parametric design intent is resolved before CAD generation. The CAD engine still receives concrete numeric dimensions.

## Parameters

Parameters are typed records with:

- ID
- name
- numeric value
- unit
- role: driving or derived
- editable flag
- source

Driving parameters are user-editable. Derived parameters are calculated from safe expression nodes.

## Relationships

Supported relationship families include:

- fixed parameter binding
- dependent dimensions
- edge offsets
- centered placement
- alignment
- symmetry
- equal spacing
- relative position

Relationships can target template fields and operation-plan fields.

## Safe Expressions

Expression nodes are explicitly modeled. Supported forms:

- literal
- parameter reference
- add
- subtract
- multiply
- divide
- min
- max

There is no free-form expression evaluation.

## Resolution

The resolver:

- validates parameter references
- builds a dependency graph
- rejects dependency cycles
- computes derived values in topological order
- applies relationships to a copy of the model
- reports diagnostics and conflicts

## Migration

Operation plans are normalized through schema versions `1.0`, `1.1`, and `1.2`. Current plans default to `1.2`.

Examples live in `plans/parametric_*.json`.
