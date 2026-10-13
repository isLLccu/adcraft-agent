"""本地 SQLite 持久化。AI 核心只接收普通 dict，不知道此模块存在。"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import threading
import uuid


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def fingerprint(value: dict) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class IdempotencyConflict(ValueError):
    pass


class Repository:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "adcraft.sqlite3"
        self.lock = threading.RLock()
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
              CREATE TABLE IF NOT EXISTS objects (
                kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
                PRIMARY KEY(kind,id));
              CREATE TABLE IF NOT EXISTS requests (
                scope TEXT NOT NULL, request_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
                kind TEXT NOT NULL, object_id TEXT NOT NULL,
                PRIMARY KEY(scope,request_key));
            """)

    @contextmanager
    def connection(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=10)
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def get(self, kind: str, item_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT data FROM objects WHERE kind=? AND id=?", (kind, item_id)).fetchone()
            return json.loads(row[0]) if row else None

    def put(self, kind: str, value: dict) -> dict:
        with self.connection() as db:
            db.execute("INSERT INTO objects(kind,id,data) VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data", (kind, value["id"], json.dumps(value, ensure_ascii=False)))
        return value

    def list(self, kind: str, limit: int | None = None, offset: int = 0) -> list[dict]:
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
            raise ValueError("limit 应为非负整数或 None")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset 应为非负整数")
        sql = "SELECT data FROM objects WHERE kind=? ORDER BY rowid"
        params: list = [kind]
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params += [limit, offset]
        elif offset:
            sql += " LIMIT -1 OFFSET ?"
            params.append(offset)
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute(sql, params)]

    def delete(self, kind: str, item_id: str) -> bool:
        with self.connection() as db:
            return db.execute("DELETE FROM objects WHERE kind=? AND id=?", (kind, item_id)).rowcount > 0

    def mutate(self, kind: str, item_id: str, mutate_fn) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data FROM objects WHERE kind=? AND id=?", (kind, item_id)).fetchone()
            if not row:
                raise KeyError(item_id)
            data = json.loads(row[0])
            mutate_fn(data)
            data["updated_at"] = now()
            db.execute("UPDATE objects SET data=? WHERE kind=? AND id=?", (json.dumps(data, ensure_ascii=False), kind, item_id))
            return data

    def create_idempotent(self, kind: str, value: dict, scope: str, key: str, content_hash: str) -> tuple[dict, bool]:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT fingerprint,kind,object_id FROM requests WHERE scope=? AND request_key=?", (scope, key)).fetchone()
            if old:
                if old[0] != content_hash:
                    raise IdempotencyConflict("同一个 request_id 不能对应不同请求内容")
                row = db.execute("SELECT data FROM objects WHERE kind=? AND id=?", (old[1], old[2])).fetchone()
                return json.loads(row[0]), False
            db.execute("INSERT INTO objects VALUES(?,?,?)", (kind, value["id"], json.dumps(value, ensure_ascii=False)))
            db.execute("INSERT INTO requests VALUES(?,?,?,?,?)", (scope, key, content_hash, kind, value["id"]))
            return value, True

    def add_trace(self, run_id: str, event: dict) -> dict:
        def update(data):
            event["id"] = len(data["trace"]) + 1
            data["trace"].append(event)
        return self.mutate("runs", run_id, update)

    def recover_interrupted(self) -> None:
        for kind in ("runs", "image_jobs"):
            for item in self.list(kind):
                if item["status"] in {"queued", "running"}:
                    item.update(status="failed", error="服务重启中断了本次任务，请重新提交。", updated_at=now())
                    self.put(kind, item)
