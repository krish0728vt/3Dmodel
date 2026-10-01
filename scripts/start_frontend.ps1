<#
.SYNOPSIS
    Run only the Vite dev server. For the full workspace use start.ps1 -Dev.
.DESCRIPTION
    Kept for debugging the frontend alone. It expects a backend already running
    on the port Vite proxies to, and does not register with the launcher's
    process state, so `stop.ps1` will not manage it.
#>
[CmdletBinding()]
param([int]$Port = 5173)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_shah_common.ps1")

$webDir = Join-Path (Get-ShahRepoRoot) "web"
Write-Host "Frontend only. For the full workspace use .\scripts\start.ps1 -Dev" -ForegroundColor DarkGray

Push-Location $webDir
try {
    npm.cmd run dev -- --port $Port --strictPort
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
