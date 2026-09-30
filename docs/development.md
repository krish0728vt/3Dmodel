# Development

## Setup

```powershell
.\.venv311\Scripts\Activate.ps1
pip install -r requirements.txt
cd web
npm.cmd install
```

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

Backend:

```powershell
.\.venv311\Scripts\python -m pytest
```

Frontend:

```powershell
cd web
npm.cmd test
npm.cmd run build
```

## Coding Rules

- Prefer schema changes over parser shortcuts.
- Keep operation IDs stable and explicit.
- Validate before geometry generation when possible.
- Record failures with normalized categories.
- Add focused tests for every new route, model, and geometry behavior.
- Keep docs close to the domain they describe.

## Security Checks

Useful local scans:

- Search for dynamic evaluation calls.
- Search for arbitrary process execution calls.
- Search for subprocess calls that enable shell interpretation.
- Search `web/src` for secret-like API key or bearer-token strings.
