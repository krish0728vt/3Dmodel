$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$RepoRoot\scripts\start_backend.ps1`""
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$RepoRoot\scripts\start_frontend.ps1`""

Write-Host "Started backend and frontend dev servers."
