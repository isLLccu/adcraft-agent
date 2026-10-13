"""端到端冒烟：跑一次 demo 生成，打印结构化日志行与 trace intent。

仅用于本地验证，不属于交付接口。
"""
import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://localhost:8000/api/v1/ai"


def main() -> int:
    with httpx.Client(timeout=30) as http:
        session = http.post(f"{BASE}/sessions").json()
        run = http.post(f"{BASE}/runs", json={
            "session_id": session["id"], "product_id": "p-cup",
            "message": "生成商品文案", "platform": "xiaohongshu", "request_id": "smoke-3",
        }).json()
        for _ in range(30):
            current = http.get(f"{BASE}/runs/{run['id']}").json()
            if current["status"] not in {"queued", "running"}:
                break
            time.sleep(0.5)
        started = next(e for e in current["trace"] if e["type"] == "started")
        print("status:", current["status"])
        print("intent:", started["data"]["intent"])
        print("answer:", current["answer"][:40])
    logs = sorted(Path("data/runtime/logs").glob("run-*.jsonl"))
    print("log-lines:")
    for path in logs:
        for line in path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry.get("run_id") == run["id"]:
                print(" ", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
