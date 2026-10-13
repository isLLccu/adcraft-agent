"""Atomic local request deduplication and recoverable persistent state."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.ai.repository import IdempotencyConflict, Repository, fingerprint


def test_concurrent_connections_create_one_local_task_and_replay_persistently(tmp_path):
    repositories = [Repository(tmp_path) for _ in range(6)]
    request_hash = fingerprint({"message": "生成文案", "product": "p-cup"})

    def submit(index):
        return repositories[index].create_idempotent("runs", {"id": f"candidate-{index}", "status": "queued"},
                                                     "session-1", "request-1", request_hash)

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(submit, range(6)))
    assert sum(fresh for _, fresh in results) == 1
    assert len({run["id"] for run, _ in results}) == 1
    reopened = Repository(tmp_path)
    assert len(reopened.list("runs")) == 1
    persisted, fresh = reopened.create_idempotent("runs", {"id": "never-created"}, "session-1", "request-1", request_hash)
    assert not fresh and persisted == results[0][0]
    with pytest.raises(IdempotencyConflict):
        reopened.create_idempotent("runs", {"id": "conflicting"}, "session-1", "request-1", fingerprint({"message": "不同内容"}))
    assert len(reopened.list("runs")) == 1


def test_failure_recovery_preserves_completed_outputs_and_provider_references(tmp_path):
    repository = Repository(tmp_path)
    repository.put("runs", {"id": "done", "status": "completed", "answer": "保留结果"})
    repository.put("runs", {"id": "queued", "status": "queued", "trace": []})
    repository.put("image_jobs", {"id": "active", "status": "running", "images": [{"index": 0}],
                                  "provider_tasks": [{"index": 1, "task_id": "external-id"}]})
    repository.put("image_jobs", {"id": "partial", "status": "partial", "images": [{"index": 0}]})
    Repository(tmp_path).recover_interrupted()
    assert repository.get("runs", "done") == {"id": "done", "status": "completed", "answer": "保留结果"}
    assert repository.get("runs", "queued")["status"] == "failed"
    active = repository.get("image_jobs", "active")
    assert active["status"] == "failed"
    assert active["images"] == [{"index": 0}]
    assert active["provider_tasks"] == [{"index": 1, "task_id": "external-id"}]
    assert repository.get("image_jobs", "partial")["status"] == "partial"
