# 本地一键门禁（Windows PowerShell 版），与 scripts/ci.sh 检查项一致。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\ci.ps1
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host '== 1/4 ruff =='
python -m ruff check backend/app/ai

Write-Host '== 2/4 pytest（含覆盖率）=='
python -m pytest -q

Write-Host '== 3/4 前端 lint =='
npm --prefix frontend ci
npm --prefix frontend run lint

Write-Host '== 4/4 前端构建 =='
npm --prefix frontend run build

Write-Host 'CI 全绿。'
