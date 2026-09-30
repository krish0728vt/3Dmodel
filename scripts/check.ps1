$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (Test-Path ".\.venv311\Scripts\python.exe") {
  & .\.venv311\Scripts\python.exe scripts\check_all.py @args
} else {
  python scripts\check_all.py @args
}
