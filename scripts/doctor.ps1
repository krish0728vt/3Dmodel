<#
.SYNOPSIS
    Run SHAH environment diagnostics without changing anything.
.EXAMPLE
    .\scripts$name.ps1
#>
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_shah_common.ps1")

$arguments = @("doctor")
if ($Rest) { $arguments += $Rest }

exit (Invoke-ShahPython -RepoRoot (Get-ShahRepoRoot) -Arguments $arguments)
