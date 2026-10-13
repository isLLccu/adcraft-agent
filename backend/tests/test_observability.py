"""结构化日志：白名单字段、敏感内容丢弃、按天滚动。"""
import json
from datetime import datetime, timezone

from app.ai.observability import RUN_FIELDS, RunLogger


def lines(logger):
    files = sorted(logger.directory.glob("run-*.jsonl"))
    return [json.loads(line) for file in files for line in file.read_text(encoding="utf-8").splitlines()]


def test_writes_one_json_object_per_line_with_whitelisted_fields(tmp_path):
    logger = RunLogger(tmp_path / "logs")
    logger.write({"event": "run_finished", "run_id": "run-1", "mode": "demo", "intent": "generate",
                  "status": "completed", "input_tokens": 12, "output_tokens": 34,
                  "latency_ms": 500, "error_code": None})
    entries = lines(logger)
    assert len(entries) == 1
    assert entries[0]["run_id"] == "run-1"
    assert entries[0]["input_tokens"] == 12
    assert entries[0]["ts"]
    assert set(entries[0]) <= RUN_FIELDS


def test_sensitive_fields_are_dropped_even_when_accidentally_passed(tmp_path):
    logger = RunLogger(tmp_path / "logs")
    logger.write({"run_id": "run-1", "status": "failed", "intent": "generate",
                  "prompt": "secret instructions", "response": {"body": "secret"},
                  "url": "https://upstream.example/x", "api_key": "sk-secret"})
    entry = lines(logger)[0]
    assert "prompt" not in entry and "response" not in entry
    assert "url" not in entry and "api_key" not in entry
    assert entry["run_id"] == "run-1" and entry["status"] == "failed"


def test_daily_rotation_uses_clock_date(tmp_path):
    clock = iter([
        datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
    ])
    logger = RunLogger(tmp_path / "logs", clock=lambda: next(clock))
    logger.write({"run_id": "run-a", "status": "completed"})
    logger.write({"run_id": "run-b", "status": "failed"})
    assert (tmp_path / "logs" / "run-20260101.jsonl").is_file()
    assert (tmp_path / "logs" / "run-20260102.jsonl").is_file()
    assert len(lines(logger)) == 2
