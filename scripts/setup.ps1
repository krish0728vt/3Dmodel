<#
.SYNOPSIS
    First-run setup for the SHAH INDUSTRIES workspace.
.DESCRIPTION
    Creates the .venv311 environment if needed, installs Python and frontend
    dependencies, prepares runtime directories, and initializes local
    databases. Safe to run repeatedly: existing components are detected and
    .env is never overwritten.
.EXAMPLE
    .\scripts\setup.ps1
.EXAMPLE
    .\scripts\setup.ps1 -RepairFrontend
#>
[CmdletBinding()]
param(
    [switch]$SkipPython,
    [switch]$SkipFrontend,
    [switch]$RepairFrontend
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_shah_common.ps1")

$repoRoot = Get-ShahRepoRoot
$venvPython = Join-Path $repoRoot ".venv311\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating the Python 3.11 environment (.venv311)..."
    $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($null -eq $pyLauncher) {
        Write-Host ""
        Write-Host "Python 3.11 could not be located." -ForegroundColor Red
        Write-Host "Install Python 3.11 from https://www.python.org/downloads/ and run setup again."
        Write-Host "The 'py' launcher is used so the version is selected explicitly."
        exit 1
    }
    Push-Location $repoRoot
    try {
        & py -3.11 -m venv ".venv311"
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "Could not create the environment with 'py -3.11'." -ForegroundColor Red
            Write-Host "Confirm Python 3.11 is installed: py -0p"
            exit 1
        }
    } finally {
        Pop-Location
    }
    Write-Host "Environment created."
    Write-Host ""
}

$arguments = @("setup")
if ($SkipPython) { $arguments += "--skip-python" }
if ($SkipFrontend) { $arguments += "--skip-frontend" }
if ($RepairFrontend) { $arguments += "--repair-frontend" }

exit (Invoke-ShahPython -RepoRoot $repoRoot -Arguments $arguments)
