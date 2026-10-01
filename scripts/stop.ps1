<#
.SYNOPSIS
    Stop the running SHAH session (only launcher-started processes).
.EXAMPLE
    .\scripts$name.ps1
#>
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_shah_common.ps1")

$arguments = @("stop")
if ($Rest) { $arguments += $Rest }

exit (Invoke-ShahPython -RepoRoot (Get-ShahRepoRoot) -Arguments $arguments)
