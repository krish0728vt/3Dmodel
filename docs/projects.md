# Project Workflow

The workspace treats projects and assemblies as managed local records with immutable revisions. Lifecycle actions change the record around the revisions; they do not rewrite prior CAD history.

## Project Browser

The web Design Tree includes:

- search by project name or ID
- status filters for active, archived, or all projects
- sorting by updated time, opened time, name, or created time
- thumbnail previews from local API placeholder assets
- quick actions for rename, duplicate, archive/unarchive, and delete

Opening a project updates `last_opened_at`, which makes recently opened sorting deterministic.

## Project Actions

Rename changes only the project display name.

Duplicate creates a new project record from the source revision and copies the available STEP/STL artifacts for that revision. The duplicate starts as its own active project with independent future revisions.

Archive hides a project from the default active view while preserving the database record, revisions, material assignment, and generated outputs. Unarchive restores it to the active view.

Delete requires explicit confirmation through the API and web dialog. The backend removes the project database rows and deletes only the controlled local output directory for that project under `outputs/projects/<project_id>`.

## Assembly Actions

Assemblies support the same workflow pattern:

- rename
- duplicate
- archive/unarchive
- delete with confirmation

Assembly deletion removes the assembly rows and only the controlled `outputs/assemblies/<assembly_id>` directory.

## API Routes

Project lifecycle:

- `GET /api/projects?search=&status=&sort=`
- `PATCH /api/projects/{project_id}`
- `POST /api/projects/{project_id}/rename`
- `POST /api/projects/{project_id}/duplicate`
- `POST /api/projects/{project_id}/archive`
- `POST /api/projects/{project_id}/unarchive`
- `DELETE /api/projects/{project_id}`

Assembly lifecycle:

- `GET /api/assemblies?search=&status=&sort=`
- `PATCH /api/assemblies/{assembly_id}`
- `POST /api/assemblies/{assembly_id}/rename`
- `POST /api/assemblies/{assembly_id}/duplicate`
- `POST /api/assemblies/{assembly_id}/archive`
- `POST /api/assemblies/{assembly_id}/unarchive`
- `DELETE /api/assemblies/{assembly_id}`

Delete requests require:

```json
{
  "confirmation": "DELETE"
}
```

## CLI

Projects:

```powershell
.\.venv311\Scripts\python app.py project list
.\.venv311\Scripts\python app.py project rename <project_id> "New name"
.\.venv311\Scripts\python app.py project duplicate <project_id>
.\.venv311\Scripts\python app.py project archive <project_id>
.\.venv311\Scripts\python app.py project unarchive <project_id>
.\.venv311\Scripts\python app.py project delete <project_id>
```

Assemblies:

```powershell
.\.venv311\Scripts\python app.py assembly list
.\.venv311\Scripts\python app.py assembly rename <assembly_id> "New name"
.\.venv311\Scripts\python app.py assembly duplicate <assembly_id>
.\.venv311\Scripts\python app.py assembly archive <assembly_id>
.\.venv311\Scripts\python app.py assembly unarchive <assembly_id>
.\.venv311\Scripts\python app.py assembly delete <assembly_id>
```

The delete commands ask for `DELETE` before removing local records.

## Shortcuts

The web workspace supports:

- `Ctrl+K`: focus the design prompt
- `Ctrl+Z`: undo project revision
- `Ctrl+Shift+Z`: redo project revision
- `Esc`: clear selection or close overlays
- `?`: show shortcut help
