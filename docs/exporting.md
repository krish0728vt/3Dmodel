# Exporting

Milestone 15 centralizes engineering file export under the `exports/` package.

## Supported Formats

STEP:

- primary engineering CAD format
- revision-aware filenames
- non-empty file validation
- project revision round-trip import check through CadQuery/OpenCascade
- feature history is not preserved

STL:

- mesh preview and manufacturing interchange
- quality presets: `draft`, `standard`, `high`
- metadata includes triangle count, file size, and bounding box when available

DXF:

- 2D structured sketch export only
- intended for sketches, profiles, and laser-cut style geometry
- uses millimeters
- simple layers: `OUTLINE`, `HOLES`, `CONSTRUCTION`
- arbitrary 3D solid to DXF is intentionally not claimed

Manifest:

- JSON summary of source, revision, formats, checksums, units, engineering metadata, parameters, and assembly components
- secrets are not included

ZIP:

- optional package containing selected export files plus manifest
- created with Python `zipfile`

## Deferred Formats

GLB and OBJ are deferred. CadQuery in this environment does not expose a reliable local GLB or OBJ exporter. The API rejects those requests clearly instead of producing brittle or fake files.

## Filenames

Filenames use sanitized source names and exact revision numbers:

```text
motor_mount_rev_004.step
gearbox_assembly_rev_003.stl
```

Exports are written under:

```text
outputs/exports/<source_id>/rev_004/
```

Path traversal and absolute path injection are rejected. Exports never write to uncontrolled remote destinations.

## Checksums

Every export result records a SHA-256 checksum. This is for reproducibility and file identity, not cryptographic signing.

## Batch Export

One request can produce multiple files:

```json
{
  "source_type": "project_revision",
  "source_id": "proj_123",
  "revision": 4,
  "formats": ["step", "stl", "dxf"],
  "options": {
    "stl_quality": "high",
    "package": true,
    "include_manifest": true
  }
}
```

## Assemblies

Assembly export supports:

- manifest JSON
- transformed STEP where the CAD kernel can export the visible solids
- merged STL using the selected tessellation quality
- component metadata in the manifest

Component coordinates are explicit:

- `local`
- `assembly_positioned`

The UI currently uses `assembly_positioned`.

## API

- `POST /api/exports`
- `GET /api/exports/{export_id}`
- `GET /api/exports/{export_id}/download`
- `GET /api/projects/{project_id}/exports`
- `GET /api/assemblies/{assembly_id}/exports`
- `POST /api/projects/{project_id}/revisions/{revision}/export`

Legacy links remain:

- `GET /api/projects/{project_id}/download/step`
- `GET /api/projects/{project_id}/download/stl`

## CLI

```powershell
.\.venv311\Scripts\python app.py export project <project_id> --revision 4 --format step stl
.\.venv311\Scripts\python app.py export assembly <assembly_id> --revision 2 --format step stl --package
.\.venv311\Scripts\python app.py export capability outputs/capabilities/spur_gear/example.step --format step stl
.\.venv311\Scripts\python app.py export package <project_id> --revision 4 --format step stl
```

## Limitations

- STEP round-trip checks compare volume and bounding box, not feature history.
- Assembly STEP export depends on what the CAD kernel can export from the visible transformed solids.
- DXF is limited to structured XY sketches.
- GLB and OBJ are deferred.
