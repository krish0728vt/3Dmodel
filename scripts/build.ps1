<#
.SYNOPSIS
    Typecheck and build the SHAH INDUSTRIES frontend for local production mode.
.EXAMPLE
    .\scripts\build.ps1
.EXAMPLE
    .\scripts\build.ps1 -Tests
#>
[CmdletBinding()]
param([switch]$Tests, [switch]$SkipTypecheck)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_shah_common.ps1")

$arguments = @("build")
if ($Tests) { $arguments += "--tests" }
if ($SkipTypecheck) { $arguments += "--skip-typecheck" }

exit (Invoke-ShahPython -RepoRoot (Get-ShahRepoRoot) -Arguments $arguments)
