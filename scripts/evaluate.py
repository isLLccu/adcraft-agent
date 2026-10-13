#!/usr/bin/env python3
"""Default: 24 offline regression cases. No API call without both live flags."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.ai.config import AISettings  # noqa: E402
from app.ai.evaluation import run_selected_evaluation  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="AdCraft regression evaluation; offline by default")
    parser.add_argument("--live", action="store_true", help="Run real LLM workflow cases (paid API)")
    parser.add_argument("--confirm-paid", action="store_true", help="Explicitly accept possible LLM/Embedding charges")
    parser.add_argument("--limit", type=int, help="Number of cases; default 24 offline / 2 live. Each live case may involve several API calls.")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "evaluation_report.json")
    args = parser.parse_args()
    if args.live and not args.confirm_paid:
        parser.error("--live requires --confirm-paid; no API request has been made")
    products = json.loads((PROJECT_ROOT / "data" / "sample_products.json").read_text(encoding="utf-8"))
    documents = json.loads((PROJECT_ROOT / "data" / "sample_documents.json").read_text(encoding="utf-8"))
    try:
        report = await run_selected_evaluation(AISettings(), products, documents, live=args.live, confirm_paid=args.confirm_paid, limit=args.limit)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": report["mode"], "cases_total": report["cases_total"], "passed": report["passed"], "failed": report["failed"], "report": str(args.output.resolve())}, ensure_ascii=False))
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
