# Shared helpers for the SHAH INDUSTRIES PowerShell entry points.
# Dot-source this; it defines Get-ShahRepoRoot and Get-ShahPython.

function Get-ShahRepoRoot {
    # The repo root is the parent of the scripts/ directory holding this file.
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-ShahPython {
    param([string]$RepoRoot)

    $venvPython = Join-Path $RepoRoot ".venv311\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    return $null
}

function Invoke-ShahPython {
    # Runs app.py with the project interpreter, or explains how to create it.
    param(
        [string]$RepoRoot,
        [string[]]$Arguments
    )

    $python = Get-ShahPython -RepoRoot $RepoRoot
    if ($null -eq $python) {
        Write-Host "The project environment (.venv311) was not found." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Create it and install dependencies by running:"
        Write-Host "    .\scripts\setup.ps1"
        return 1
    }

    Push-Location $RepoRoot
    try {
        & $python "app.py" @Arguments
        return $LASTEXITCODE
    } finally {
        Pop-Location
    }
}
