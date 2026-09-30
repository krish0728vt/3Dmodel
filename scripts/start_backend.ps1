$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (Test-Path ".\.venv311\Scripts\python.exe") {
  & .\.venv311\Scripts\python.exe -m uvicorn api.server:app --reload
} else {
  python -m uvicorn api.server:app --reload
}
