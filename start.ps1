# Start DataLens backend + frontend together.
# Usage: .\start.ps1
# First-time setup: .\start.ps1 -Setup

param(
    [switch]$Setup
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($Setup -or -not (Test-Path "node_modules")) {
    Write-Host "Running first-time setup..." -ForegroundColor Cyan
    npm run setup
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host ""
Write-Host "Starting DataLens..." -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  Backend:  http://localhost:8000"
Write-Host "  API docs: http://localhost:8000/docs"
Write-Host ""

npm start
