# Development

## Setup

```powershell
.\.venv311\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
cd web
npm.cmd ci
```

`requirements.txt` holds runtime dependencies; `requirements-dev.txt` holds the test
and lint tooling (`pytest`, `ruff`). Install both for development.

Python 3.11 is the supported runtime. The repository includes `.python-version` for tools that read it, but the explicit commands above remain the source of truth.

## Run

API:

```powershell
.\.venv311\Scripts\python -m uvicorn api.server:app --reload
```

Web:

```powershell
cd web
npm.cmd run dev
```

## Test

Run the full local gate:

```powershell
.\.venv311\Scripts\python scripts/check_all.py
```

Or from PowerShell:

```powershell
.\scripts\check.ps1
```

The check runner executes:

- Python lint (`ruff check .`)
- workflow lint (`actionlint` over `.github/workflows`)
- Python tests
- deterministic evaluation smoke benchmark
- evaluation baseline comparison
- frontend typecheck
- frontend tests
- frontend production build
- repository security scan

Target a group while iterating:

```powershell
.\.venv311\Scripts\python scripts/check_all.py --only lint
.\.venv311\Scripts\python scripts/check_all.py --only workflows
.\.venv311\Scripts\python scripts/check_all.py --only python
.\.venv311\Scripts\python scripts/check_all.py --only frontend
.\.venv311\Scripts\python scripts/check_all.py --only evaluation
.\.venv311\Scripts\python scripts/check_all.py --only security
```

Backend tests:

```powershell
.\.venv311\Scripts\python -m pytest
```

`pytest.ini` sets `addopts = -m "not live" --strict-markers`, so the default suite is
hermetic. Markers: `live` (needs API keys, MCP, or internet), `integration`, `slow`.
Run live tests deliberately:

```powershell
.\.venv311\Scripts\python -m pytest -m live
```

Evaluation:

```powershell
.\.venv311\Scripts\python app.py evaluate smoke
.\.venv311\Scripts\python app.py evaluate compare
```

Frontend:

```powershell
cd web
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

`npm run typecheck` is `tsc --noEmit`. `npm test` runs Vitest once (`vitest run`);
`npm run test:watch` watches. Unit tests cover the pure formatting and unit-conversion
helpers and live beside their source as `*.test.ts`.

The frontend build currently emits a known large chunk warning from the Three.js/CAD viewer bundle. Treat build errors as failures, but the current warning is tracked technical debt and does not fail CI.

## GitHub Actions

CI runs on pushes and pull requests to `main`, and can be started manually through `workflow_dispatch`.

Jobs:

- `python-tests`: Python 3.11, system CAD libraries, `pip install -r requirements.txt -r requirements-dev.txt`, `ruff check .`, `python -m pytest` (JUnit XML uploaded as an artifact)
- `frontend-tests`: Node 22, `npm ci`, typecheck, Vitest, production build
- `evaluation-smoke`: deterministic `python app.py evaluate smoke` and baseline compare
- `security-checks`: `actionlint` workflow validation and the repository security scan

### CadQuery In CI

CadQuery is installed with plain `pip` on `ubuntu-latest`. This works because
`cadquery-ocp` publishes `cp311` `manylinux_2_28` wheels, and `cadquery` pins
`cadquery-ocp<8.0,>=7.9.3.1`, so CI resolves the same OpenCascade minor version used
locally. Conda/Mamba is therefore unnecessary. The jobs install `libgl1`, `libegl1`,
and `libxrender1` via apt because OpenCascade links against them even for headless
geometry work. If a future CadQuery release stops shipping manylinux wheels, switch
those jobs to a Conda-based setup rather than pinning an old release.

### Isolation

The Python jobs point `SHAH_LEARNING_DB_PATH` at the runner temp directory so CI never
touches a developer database. The evaluation runner wipes `outputs/evaluation/work` on
every run and uses a per-run isolated `projects.db`, so the smoke suite is
self-contained. No test depends on an absolute user-specific path.

CI does not require `OPENAI_API_KEY`, a live MCP server, a browser, GUI access, or live external capability services. Any future test requiring live network/API access must be marked with the `live` pytest marker and kept out of default CI.

Recommended branch protection:

- require the CI workflow before merging to `main`
- require pull requests for non-trivial changes
- require review of dependency update PRs

## Lint

`ruff` is configured in `ruff.toml` with a deliberately conservative rule set: real
errors (`E4`, `E7`, `E9`), all of pyflakes (`F`), and three high-value bugbear rules
(mutable default arguments, `break`/`return` in `finally`, `hasattr(__call__)` misuse).
Style rules beyond that are intentionally excluded so CI stays signal rather than noise.

```powershell
.\.venv311\Scripts\python -m ruff check .
```

`app.py` carries a scoped `E402` ignore because it quiets `fontTools` logging before
importing CadQuery. `ruff format` is available for new files but is **not** enforced in
CI, so the repository is not mass-formatted.

Workflow files are linted with `actionlint`, which catches invalid action inputs and
context misuse that GitHub only reports by failing the run with zero jobs scheduled:

```powershell
.\.venv311\Scripts\python scripts/check_all.py --only workflows
```

Always run this before pushing a workflow change. Note that the `runner` context is
unavailable in a job-level `env:` block; use `github.workspace` there, or set the
variable on the individual step.

## Dependencies

Runtime dependencies live in `requirements.txt`; development and CI tooling lives in
`requirements-dev.txt`. Version floors are the versions the project is verified
against rather than hard pins, so Dependabot can propose upgrades that CI then gates.

Frontend dependencies are locked by `web/package-lock.json`. Use `npm ci` in CI and when validating a clean install.

Dependabot checks Python, npm, and GitHub Actions weekly. Dependency PRs should pass tests, build, and evaluation smoke before merge; no automatic merge is configured.

## Commit Workflow

Recommended local flow:

1. Implement the change.
2. Run `python scripts/check_all.py`.
3. Review `git diff`.
4. Confirm no generated outputs, local DBs, or secrets are staged.
5. Commit.
6. Push.

## Coding Rules

- Prefer schema changes over parser shortcuts.
- Keep operation IDs stable and explicit.
- Validate before geometry generation when possible.
- Record failures with normalized categories.
- Add focused tests for every new route, model, and geometry behavior.
- Keep docs close to the domain they describe.

## Security Checks

Reusable local scan:

```powershell
.\.venv311\Scripts\python scripts/security_check.py
```

The scan checks source files for dynamic evaluation calls, process execution with shell interpretation, token-like private key patterns, and frontend secret markers. It intentionally avoids failing on documentation that names environment variables for setup guidance.

## Deliberate Tooling Omissions

These were considered for the CI milestone and intentionally left out to keep the
toolchain small. Each is a reversible decision, not an oversight.

- **Repository-wide formatting** (`ruff format` / `black`): would produce a very large
  diff across unrelated files. `ruff format` is configured but unenforced; formatting
  can be adopted per-file over time.
- **Frontend ESLint**: would add several dev dependencies and a flat-config setup for
  little gain over `tsc --strict`, which already runs in CI. Worth adding when the
  frontend grows shared conventions that types cannot express.
- **`pytest-cov` coverage**: the suite is a geometry pipeline where line coverage is a
  weak signal, and a reporting-only number nobody acts on is noise. Add it with
  `--cov-report=term-missing` and no threshold if a coverage gap needs tracking.
- **`pre-commit` hooks**: the meaningful checks here (CadQuery tests, evaluation smoke)
  are far too slow for a commit hook, and hooks limited to whitespace fixes do not
  justify the extra install step. `scripts/check_all.py` is the gate instead.
- **Branch protection automation**: configuring it requires admin credentials, so the
  recommended settings are documented above and applied by hand.
- **CODEOWNERS**: no verified owner mapping exists for this repository.

## Known Technical Debt

- The production web bundle ships a single ~800 kB JS chunk dominated by Three.js and
  emits Vite's chunk-size warning. The build succeeds and CI does not fail on it.
  Splitting the viewer out behind a dynamic import is the intended fix.
