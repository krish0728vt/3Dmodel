# Local Deployment

SHAH INDUSTRIES runs as a local, single-user workspace. Setup is two commands.

## Supported Environment

| Component | Requirement |
| --- | --- |
| OS | Windows 10 / 11 (primary). The Python layer is cross-platform. |
| Python | 3.11 (the `py -3.11` launcher selects it explicitly) |
| Node.js | current LTS, 20 or newer |
| CAD kernel | CadQuery with OpenCascade, installed from PyPI wheels |

Python 3.11 is a hard requirement, not a preference: the CadQuery/OpenCascade
wheels the project depends on are built per minor version.

## Windows Setup

```powershell
git clone https://github.com/krish0728vt/3Dmodel.git
cd 3Dmodel
.\scripts\setup.ps1
.\scripts\start.ps1
```

`setup.ps1` creates `.venv311` with `py -3.11` when it is missing, installs
Python and frontend dependencies, creates `data/`, `outputs/`, `runtime/`, and
`runtime/logs/`, copies `.env.example` to `.env` if you have no `.env` yet, and
initializes the local databases. It is idempotent: running it again detects what
is already installed and never overwrites `.env`.

You can also double-click `START_SHAH.bat` (production) or `DEV_SHAH.bat`
(development). Both resolve the repository from their own location, so the
checkout can live anywhere.

## Running

### Local production mode (default)

```powershell
.\scripts\start.ps1
```

One origin serves everything, which is the simplest way to use the app:

| URL | Serves |
| --- | --- |
| `http://127.0.0.1:8000/` | the built frontend |
| `http://127.0.0.1:8000/api/...` | the API |

FastAPI mounts `web/dist` and adds an SPA fallback, so deep links such as
`/projects/<id>` load correctly. Because everything is same-origin, this mode
does not depend on CORS at all.

Production mode needs a build. If `web/dist` is missing the launcher says so
rather than silently running a long npm command. Build explicitly, or ask for it:

```powershell
.\scripts\build.ps1
.\scripts\start.ps1 -Build        # build, then serve
```

### Development mode

```powershell
.\scripts\start.ps1 -Dev
```

Two servers, with hot reload:

| URL | Serves |
| --- | --- |
| `http://127.0.0.1:5173/` | Vite dev server (the app) |
| `http://127.0.0.1:8000/` | FastAPI with `--reload` |

Vite proxies `/api` to the backend, so the frontend uses relative URLs in both
modes. The launcher passes the backend's real address to Vite, so `-Dev` with a
non-default `-BackendPort` proxies to the backend it just started.

Press Ctrl+C to stop. The launcher terminates both children and clears its state
file; a clean shutdown exits 0.

## Commands

Every command works as `python app.py <command>` and has a PowerShell wrapper.

| Command | Purpose |
| --- | --- |
| `setup` | First-run setup (idempotent) |
| `doctor` | Read-only diagnostics |
| `serve` | Start the workspace (`--dev` / `--production`) |
| `stop` | Stop the session this launcher started |
| `status` | Recorded processes plus live API health |
| `build` | Typecheck and build the frontend, verify `dist` |
| `clean` | Remove regenerable artifacts only |
| `backup` | Archive databases and non-secret config |
| `version` | App version, build commit, Python, schema |

### Ports

Defaults are 8000 (backend) and 5173 (dev frontend).

```powershell
.\scripts\start.ps1 -BackendPort 8010 -FrontendPort 5180
.\scripts\start.ps1 -AutoPort      # take the next free port instead
```

A busy port is reported, never resolved by force:

```
ERROR:
Port 8000 is already in use.
  Use --backend-port <other-port> to pick a different port,
  or stop the process using port 8000 yourself.
  SHAH never terminates a process just because it holds a port.
```

This is deliberate. The launcher will not kill a process merely because it
occupies a port it wants -- that process may be something you care about.

### Stop and status

`stop` only ever signals PIDs recorded in `runtime/shah_processes.json`, and
re-validates each one (still alive, and still the expected program) before
signalling it. A stale file whose PID has been recycled by an unrelated program
is reported and left alone:

```
frontend (PID 18652): stale entry - that PID no longer belongs to a SHAH
process, so it was left alone
```

Children are stopped in reverse order, frontend before backend, so a running
launcher does not race the stop command.

Vite is started through `node` directly rather than `npm run dev`, so the
recorded PID *is* the dev server. The `npm.cmd` shim exits immediately and would
leave the real server as an untracked grandchild.

### Logs

`runtime/logs/` holds `backend.log` and `frontend.log`. Each session truncates
them, which keeps logs bounded without a rotation policy. They are gitignored.

When a server fails to become healthy, the launcher prints the tail of the
relevant log with the reason, rather than a traceback.

## Configuration

### Secrets

Secrets live in `.env` only, never in JSON config:

```
OPENAI_API_KEY=
```

The key is **optional**. Without it the app starts normally and reports:

```
AI NOT CONFIGURED - natural-language prompts are unavailable.
  Manual CAD, projects, assemblies, exports, and evaluation work normally.
```

Only natural-language prompt parsing needs it. Manual CAD, operation plans,
projects, revisions, parametrics, engineering checks, assemblies, exports, and
the evaluation suite are all deterministic and work without a key.

### Machine settings

Copy `config/local.example.json` to `config/local.json` to change defaults:

```json
{
  "backend_host": "127.0.0.1",
  "backend_port": 8000,
  "frontend_port": 5173,
  "open_browser": true,
  "startup_timeout": 30,
  "mode": "production"
}
```

`config/local.json` is gitignored. Put no secrets in it. An invalid file is
reported and ignored rather than blocking startup.

## Diagnostics

```powershell
.\scripts\doctor.ps1
```

`doctor` never changes system state. It reports Python and its executable, the
virtualenv, a real CadQuery/OpenCascade geometry call, Pydantic, FastAPI,
uvicorn, the OpenAI package, Node, npm, frontend dependencies and build state,
writable `outputs/` `data/` `runtime/`, database readability, `.env`, the API
key, MCP config, and port availability.

Each check reports PASS, WARN, or FAIL. Exit codes are scriptable: **0** when
ready (warnings included), **nonzero** only on a real failure. `--json` emits the
whole report as JSON.

```
[PASS] Python: 3.11.9
[PASS] CadQuery: 2.8.0 (OpenCascade geometry verified)
[PASS] Node.js: 24.14.0
[WARN] OPENAI_API_KEY: not configured - natural-language prompt parsing is unavailable
       Optional. Add OPENAI_API_KEY to .env to enable AI parsing. Manual CAD,
       projects, assemblies, exports, and evaluation work without it.

Core deterministic CAD remains available.

Overall: READY WITH WARNINGS
```

## Troubleshooting

### `npm ci` fails with EPERM on Windows

Almost always a file lock on a Rollup native binary, not a broken lockfile:

```
npm error code EPERM
npm error syscall unlink
npm error path web\node_modules\@rollup\rollup-win32-x64-msvc\rollup.win32-x64-msvc.node
```

1. Stop any running dev server: `python app.py stop`.
2. Close editors or terminals with files open under `web/node_modules`.
3. Pause antivirus scanning of the repository if it locks binaries.
4. Run setup again.

`setup` falls back to `npm install` against the existing lockfile if `npm ci` is
blocked. To rebuild the tree from scratch, ask for it explicitly:

```powershell
.\scripts\setup.ps1 -RepairFrontend
```

`node_modules` is never deleted unless you pass that flag.

### Port already in use

Use `-BackendPort` / `-FrontendPort`, or `-AutoPort`. To find the holder:

```powershell
netstat -ano | Select-String ":8000.*LISTENING"
```

### "A SHAH session is already running"

Run `python app.py status` to see what is recorded, then `python app.py stop`. If
the recorded PIDs are stale, `stop` clears the state file.

### Frontend not built

Production mode needs `web/dist`. Run `.\scripts\build.ps1`, or start with
`-Build`, or use `-Dev`.

### A database will not open

The launcher reports which one and stops. It never deletes or recreates a
database for you. Move the file aside to let it rebuild, or restore a backup.

## Backup

```powershell
python app.py backup
```

Writes `backups/shah_backup_YYYYMMDD_HHMMSS.zip` from an explicit allow-list:
the four databases, the capability registry, MCP config, and `config/local.json`
when present.

Never included: `.env`, any secret, `node_modules`, `.venv311`, runtime logs. The
whole repository is never archived.

Restore is deliberately manual for now: stop the app, move the current database
aside, and extract the file you want from the archive. An automated restore that
overwrites live databases is deferred rather than shipped half-safe.

## Clean

```powershell
python app.py clean          # lists what would be removed
python app.py clean --yes    # removes it
```

Only regenerable artifacts: `web/dist`, `outputs/evaluation/work`, and
`runtime/logs`. Databases, exports in `outputs/`, user projects, and backups are
never touched. A test and a security-scan rule both enforce that the cleanable
list excludes user-data directories.

## Security And Network Exposure

The app binds `127.0.0.1` by default. It has **no authentication, authorization,
rate limiting, or request auditing**, and is designed for local single-user use.

`--host 0.0.0.0` is available but prints a warning. Do not expose this service to
an untrusted network or the internet. A localhost development tool is not an
internet-ready application.

## Why Not Docker

Docker is **deferred**, deliberately.

CadQuery depends on OpenCascade native libraries, and the workflow this project
serves is a desktop-local one: generating CAD files into local directories,
reading and writing local SQLite databases, and opening a browser against a
local port. A container adds a build layer, volume mapping for every local
path, and an OpenCascade installation that must be kept in step with the host
wheels -- in exchange for very little, since there is no server deployment
target.

A brittle Dockerfile that exists only to claim Docker support would be worse
than none. If a genuine hosted deployment target appears, the decision is worth
revisiting; the API layer is already cleanly separated.

## Packaging

The shipped approach is a **repo-based local launcher**: the `deployment`
package plus PowerShell entry points and the `.bat` files. PyInstaller,
Electron, Tauri, and an MSI installer were all considered and rejected for this
milestone -- bundling a CAD kernel and a Node toolchain into a single-file
executable is a large, fragile undertaking, and the two-command setup above
already gets a user running. Nothing here blocks adding one later.

## Architecture Notes

| Concern | Location |
| --- | --- |
| Paths and controlled directories | `deployment/paths.py` |
| Typed check / state models | `deployment/models.py` |
| Read-only diagnostics | `deployment/checks.py` |
| Setup and installation | `deployment/bootstrap.py` |
| Port checks | `deployment/ports.py` |
| Process orchestration and state | `deployment/processes.py` |
| Health probing | `deployment/health.py` |
| Serve / stop / status / build / clean / backup | `deployment/launcher.py` |
| Static SPA serving | `api/static_frontend.py` |
| Version single source of truth | `shah_version.py` |

Orchestration is Python so it is testable and portable; PowerShell is a thin
Windows entry point that resolves the interpreter and forwards arguments. No
logic is duplicated between the two. `subprocess` is always called with an
explicit argument list and never `shell=True`.

Version and build identity come only from `shah_version.py`, which the API
(`GET /api/version`), the CLI (`app.py version`), the launcher banner, and the
frontend About panel all read.
