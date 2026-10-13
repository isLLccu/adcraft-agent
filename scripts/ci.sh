#!/usr/bin/env bash
# 本地一键门禁：与 .github/workflows/ci.yml 保持一致的检查项。
# 用法：bash scripts/ci.sh（Git Bash / Linux / macOS；Windows 也可用 scripts/ci.ps1）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== 1/4 ruff =="
python -m ruff check backend/app/ai

echo "== 2/4 pytest（含覆盖率）=="
python -m pytest -q

echo "== 3/4 前端 lint =="
npm --prefix frontend ci
npm --prefix frontend run lint

echo "== 4/4 前端构建 =="
npm --prefix frontend run build

echo "CI 全绿。"
