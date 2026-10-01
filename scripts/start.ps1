<#
.SYNOPSIS
    Start the SHAH INDUSTRIES local workspace.
.DESCRIPTION
    Production mode (default) serves the built frontend and the API from one
    origin. Development mode runs FastAPI with reload plus the Vite dev server.
.EXAMPLE
    .\scripts\start.ps1
.EXAMPLE
    .\scripts\start.ps1 -Dev
.EXAMPLE
    .\scripts\start.ps1 -Build -BackendPort 8010
#>
[CmdletBinding()]
param(
    [switch]$Dev,
    [switch]$Build,
    [switch]$NoOpen,
    [switch]$AutoPort,
    [int]$BackendPort,
    [int]$FrontendPort,
    [string]$BindHost,
    [int]$Timeout
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_shah_common.ps1")

$repoRoot = Get-ShahRepoRoot
$arguments = @("serve")

if ($Dev) { $arguments += "--dev" } else { $arguments += "--production" }
if ($Build) { $arguments += "--build" }
if ($NoOpen) { $arguments += "--no-open" }
if ($AutoPort) { $arguments += "--auto-port" }
if ($PSBoundParameters.ContainsKey("BackendPort")) { $arguments += @("--backend-port", "$BackendPort") }
if ($PSBoundParameters.ContainsKey("FrontendPort")) { $arguments += @("--frontend-port", "$FrontendPort") }
if ($PSBoundParameters.ContainsKey("BindHost")) { $arguments += @("--host", $BindHost) }
if ($PSBoundParameters.ContainsKey("Timeout")) { $arguments += @("--timeout", "$Timeout") }

exit (Invoke-ShahPython -RepoRoot $repoRoot -Arguments $arguments)
