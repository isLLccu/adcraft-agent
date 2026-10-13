"""结构化 JSON 行日志：字段白名单，按天滚动。

日志写入 data/runtime/logs/run-YYYYMMDD.jsonl。只记录白名单字段，
prompt 文本、模型响应正文、供应商 URL 和密钥即使被误传入也会被丢弃。
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .repository import now

RUN_FIELDS = {
    "ts", "event", "run_id", "session_id", "request_id", "intent", "mode",
    "status", "input_tokens", "output_tokens", "latency_ms", "error_code",
}


class RunLogger:
    """每行一个 JSON 对象；白名单之外的字段被静默丢弃。

    静默丢弃是刻意设计：调用方可以传富字典，日志器绝不转发白名单
    没有点名的内容。这与 provider 不记录响应体和密钥的基调一致。
    """

    def __init__(self, directory: Path, clock=None):
        self.directory = Path(directory)
        self._lock = threading.Lock()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _file(self) -> Path:
        return self.directory / f"run-{self._clock():%Y%m%d}.jsonl"

    def write(self, fields: dict) -> None:
        entry = {key: value for key, value in fields.items() if key in RUN_FIELDS}
        entry.setdefault("ts", now())
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            with self._file().open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
