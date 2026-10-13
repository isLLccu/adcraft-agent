"""会话锁池：同一 key 复用，最后引用释放后自动回收。"""
import asyncio
import gc
import weakref

from app.ai.locks import KeyedLocks


def test_same_key_returns_same_lock_while_referenced():
    locks = KeyedLocks()
    first = locks.get("s1")
    assert locks.get("s1") is first
    assert locks.get("s2") is not first


def test_lock_is_reclaimed_after_last_reference_drops():
    locks = KeyedLocks()
    lock = locks.get("s1")
    reference = weakref.ref(lock)
    assert reference() is lock
    del lock
    gc.collect()
    assert reference() is None
    assert len(locks._locks) == 0


def test_recreated_lock_is_a_fresh_lock():
    locks = KeyedLocks()
    lock = locks.get("s1")
    del lock
    gc.collect()
    second = locks.get("s1")
    assert isinstance(second, asyncio.Lock)
