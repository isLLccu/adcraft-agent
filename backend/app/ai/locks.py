"""按 key 的 asyncio.Lock 池：弱引用回收，防止会话锁无限增长。"""
import asyncio
import threading
import weakref


class KeyedLocks:
    """get(key) 返回该 key 的锁；最后一个持有者释放后锁可被 GC。

    原实现用普通 dict：每个 session_id 永久占用一条锁记录。改用
    WeakValueDictionary 后，任何任务持有强引用期间锁不会被回收，
    没有使用者时自动清理；并发 get 由线程锁串行化，保证同一 key
    同一时刻只有一个锁实例被创建。
    """

    def __init__(self):
        self._locks: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self._guard = threading.Lock()

    def get(self, key: str) -> asyncio.Lock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock
