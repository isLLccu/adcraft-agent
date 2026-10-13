# Local one-shot gate (Windows PowerShell version), same checks as scripts/ci.sh.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\ci.ps1
# ASCII-only source: PowerShell 5.1 reads UTF-8 files without BOM as ANSI.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
# Prefer the project venv; fall back to PATH python (used in CI images).
$Python = if (Test-Path '.venv\Scripts\python.exe') { '.venv\Scripts\python.exe' } else { 'python' }

Write-Host '== 1/4 ruff =='
& $Python -m ruff check backend/app/ai
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '== 2/4 pytest (with coverage) =='
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '== 3/4 frontend lint =='
npm --prefix frontend ci
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm --prefix frontend run lint
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '== 4/4 frontend build =='
npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host 'CI gate passed.'
