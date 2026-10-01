<#
.SYNOPSIS
    Superseded by start.ps1 -Dev. Kept so the old command still works.
.DESCRIPTION
    The launcher introduced in v0.19 adds health checks, a process state file,
    clean shutdown, and log capture. This script delegates to it rather than
    starting the servers itself, so there is one implementation.
#>
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)

$ErrorActionPreference = "Stop"

Write-Host "start_dev.ps1 now delegates to start.ps1 -Dev." -ForegroundColor Yellow
Write-Host ""

$arguments = @("-Dev")
if ($Rest) { $arguments += $Rest }

& (Join-Path $PSScriptRoot "start.ps1") @arguments
exit $LASTEXITCODE
