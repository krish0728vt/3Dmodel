# Assemblies

The Assembly Foundation stores multi-component CAD layouts without changing project revision history.

## Models

Assembly records live in `data/shah_assemblies.db` by default.

An assembly has:

- `assembly_id`
- name and notes
- current revision pointer
- created/updated timestamps

An assembly revision has:

- immutable revision ID and number
- parent revision ID
- user instruction and change summary
- component list

## Components

Supported component source types:

- `project_revision`
- `generated_file`
- `capability_output`
- `imported_file`

Each component stores:

- component ID and display name
- source metadata
- translation in millimeters
- rotation in degrees
- visibility
- grounded state
- metadata dictionary

Grounded components reject move, rotate, and set-transform edits.

## Edits

Supported edit types:

- add component
- remove component
- move component
- rotate component
- set full transform
- set visibility
- set grounded state
- rename component
- rename assembly

Every accepted edit creates a new immutable assembly revision.

## Preview

Preview returns:

- component mesh URL when available
- transformed component bounding boxes
- assembly bounding box
- visibility and grounding states

Project revision components reuse project STL export URLs.

## Engineering

Assembly engineering currently aggregates:

- component count
- known mass
- unknown-mass component IDs
- center of mass when all contributing masses are known
- transformed component bounding boxes
- coarse interference results

Interference is intentionally conservative in this milestone: world-space bounding-box overlap reports `POSSIBLE_OVERLAP`.

## Export

The primary assembly export is a manifest JSON file containing component sources and transforms.

Combined STEP/STL export is available internally for simple visible components, but manifest export is the stable interchange path for this foundation milestone.
