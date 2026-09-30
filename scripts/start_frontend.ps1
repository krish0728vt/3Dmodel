$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location "$RepoRoot\web"

npm.cmd run dev
