<#
.SYNOPSIS
    Run only the FastAPI backend. For the full workspace use start.ps1.
.DESCRIPTION
    Kept for debugging a single server. It intentionally does not register with
    the launcher's process state, so `stop.ps1` will not manage it; stop it with
    Ctrl+C in this window.
#>
[CmdletBinding()]
param([int]$Port = 8000, [string]$BindHost = "127.0.0.1")

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_shah_common.ps1")

$repoRoot = Get-ShahRepoRoot
$python = Get-ShahPython -RepoRoot $repoRoot
if ($null -eq $python) {
    Write-Host "The project environment (.venv311) was not found." -ForegroundColor Yellow
    Write-Host "Run .\scripts\setup.ps1 first."
    exit 1
}

Write-Host "Backend only. For the full workspace use .\scripts\start.ps1" -ForegroundColor DarkGray
Push-Location $repoRoot
try {
    & $python -m uvicorn api.server:app --reload --host $BindHost --port $Port
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
