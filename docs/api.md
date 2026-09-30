# API

Run the API:

```powershell
.\.venv311\Scripts\python -m uvicorn api.server:app --reload
```

## Core Routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Backend status |
| `POST` | `/api/generate` | Parse/generate a model and optionally save it |
| `GET` | `/api/materials` | List known materials |

## Projects

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/projects` | List projects |
| `GET` | `/api/projects/{project_id}` | Project detail |
| `GET` | `/api/projects/{project_id}/history` | Revision history |
| `POST` | `/api/projects/{project_id}/edit` | Apply an edit |
| `POST` | `/api/projects/{project_id}/undo` | Move active pointer to parent revision |
| `POST` | `/api/projects/{project_id}/redo` | Move active pointer to a child revision |
| `POST` | `/api/projects/{project_id}/restore/{revision}` | Restore active pointer |
| `GET` | `/api/projects/{project_id}/download/step` | Download STEP |
| `GET` | `/api/projects/{project_id}/download/stl` | Download STL |
| `GET` | `/api/projects/{project_id}/engineering` | Engineering report |
| `POST` | `/api/projects/{project_id}/material` | Set material assignment |
| `GET` | `/api/projects/{project_id}/revisions/{revision}/preview` | Semantic preview metadata |
| `GET` | `/api/projects/{project_id}/parameters` | List design parameters |
| `GET` | `/api/projects/{project_id}/relationships` | List design relationships |
| `GET` | `/api/projects/{project_id}/resolved-design` | Resolve parametric design |
| `POST` | `/api/projects/{project_id}/parameters/{parameter_id}` | Update driving parameter |

## Assemblies

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/assemblies` | List assemblies |
| `POST` | `/api/assemblies` | Create assembly and initial revision |
| `GET` | `/api/assemblies/{assembly_id}` | Assembly detail |
| `GET` | `/api/assemblies/{assembly_id}/history` | Revision history |
| `POST` | `/api/assemblies/{assembly_id}/components` | Add component |
| `POST` | `/api/assemblies/{assembly_id}/edit` | Apply structured or simple parsed edit |
| `POST` | `/api/assemblies/{assembly_id}/undo` | Restore parent revision |
| `POST` | `/api/assemblies/{assembly_id}/redo` | Restore child revision |
| `POST` | `/api/assemblies/{assembly_id}/restore/{revision}` | Restore specific revision |
| `GET` | `/api/assemblies/{assembly_id}/preview` | Component preview and bounding boxes |
| `GET` | `/api/assemblies/{assembly_id}/engineering` | Assembly engineering summary |
| `GET` | `/api/assemblies/{assembly_id}/download` | Manifest download |

## Learning And Capabilities

See [Learning Core](learning-core.md) and [Capabilities](capabilities.md) for route details.
