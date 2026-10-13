"""端到端冒烟：跑一次生成（默认 live 继承 .env 配置），打印结构化日志行与 trace。

用法：python scripts/smoke_log.py [message] [request_id] [session_id]
仅用于本地验证，不属于交付接口。密钥不会出现在任何输出里。
"""
import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://localhost:8000/api/v1/ai"


def main() -> int:
    message = sys.argv[1] if len(sys.argv) > 1 else "生成商品文案"
    request_id = sys.argv[2] if len(sys.argv) > 2 else f"smoke-{int(time.time())}"
    session_id = sys.argv[3] if len(sys.argv) > 3 else None
    with httpx.Client(timeout=120) as http:
        if not session_id:
            session_id = http.post(f"{BASE}/sessions").json()["id"]
        run = http.post(f"{BASE}/runs", json={
            "session_id": session_id, "product_id": "p-cup",
            "message": message, "platform": "xiaohongshu", "request_id": request_id,
        }).json()
        for _ in range(240):
            current = http.get(f"{BASE}/runs/{run['id']}").json()
            if current["status"] not in {"queued", "running"}:
                break
            time.sleep(0.5)
        started = next(e for e in current["trace"] if e["type"] == "started")
        print("status:", current["status"])
        print("intent:", started["data"]["intent"])
        print("session:", session_id)
        print("answer:", current["answer"][:60])
        if current.get("draft"):
            print("draft-title:", current["draft"]["title"])
            print("claims:", len(current["draft"]["claims"]), "evidence:", len(current["draft"]["evidence_ids"]))
        print("validation:", json.dumps(current["validation"], ensure_ascii=False))
        usage = current["usage"]
        print("usage:", json.dumps(usage, ensure_ascii=False))
        print("error:", current["error"])
    logs = sorted(Path("data/runtime/logs").glob("run-*.jsonl"))
    for path in logs:
        for line in path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry.get("run_id") == run["id"]:
                print("log:", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
