"""分布式锁抽象：单实例 / 多实例 部署可切换。

约定：
- DistributedLock Protocol：try_acquire / release；
- InMemoryLock：单进程互斥（threading.Lock），用于 v1 / 测试；
- RedisLock（占位）：v1.1 多实例时启用，依赖 redis 库；
- SchedulerJob 启动时 acquire 锁 → 跑完 release；锁未拿到则跳过本次执行。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional, Protocol

log = logging.getLogger(__name__)


class DistributedLock(Protocol):
    """分布式锁接口。"""

    def try_acquire(self, key: str, *, ttl_seconds: int = 60) -> Optional[str]:
        """尝试获取锁。

        Returns:
            token（持有证明，用于 release）或 None（未拿到）。
        """
        ...

    def release(self, key: str, token: str) -> bool:
        """释放锁（仅当 token 匹配）。Returns: True 释放成功 / False 已过期或不存在。"""
        ...


class InMemoryLock:
    """单进程互斥实现。"""

    def __init__(self) -> None:
        self._held: dict[str, str] = {}
        self._mutex = threading.Lock()

    def try_acquire(self, key: str, *, ttl_seconds: int = 60) -> Optional[str]:
        with self._mutex:
            current = self._held.get(key)
            if current is not None:
                # 已有锁持有者；检查是否过期
                if current.startswith("expired:"):
                    pass
                else:
                    return None
            token = f"mem-{id(self)}-{time.time_ns()}"
            self._held[key] = token
            return token

    def release(self, key: str, token: str) -> bool:
        with self._mutex:
            if self._held.get(key) == token:
                del self._held[key]
                return True
            return False


class RedisLock:
    """Redis 分布式锁占位实现（依赖 redis 库）。

    使用 SET NX EX + Lua release（v1.1 启用）。
    """

    def __init__(self, redis_url: str) -> None:
        try:
            import redis
        except ImportError as e:
            raise RuntimeError("redis package not installed") from e
        self._client = redis.Redis.from_url(redis_url)
        # Lua 脚本：仅当 value 匹配才删除
        self._release_script = self._client.register_script(
            """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            else
                return 0
            end
            """
        )

    def try_acquire(self, key: str, *, ttl_seconds: int = 60) -> Optional[str]:
        token = f"redis-{time.time_ns()}"
        ok = self._client.set(key, token, nx=True, ex=ttl_seconds)
        return token if ok else None

    def release(self, key: str, token: str) -> bool:
        result = self._release_script(keys=[key], args=[token])
        return bool(result)


# 进程级默认
_default_lock: Optional[DistributedLock] = None


def get_lock() -> DistributedLock:
    """返回默认锁实现（v1 默认 InMemoryLock）。"""
    global _default_lock
    if _default_lock is None:
        _default_lock = InMemoryLock()
    return _default_lock


def set_lock(lock: DistributedLock) -> None:
    """测试钩子：替换默认锁实现。"""
    global _default_lock
    _default_lock = lock


def reset_for_test() -> None:
    global _default_lock
    _default_lock = None
