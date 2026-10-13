"""分布式锁单元测试：InMemoryLock（RedisLock 通过 mock 测试）。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.scheduler.distributed_lock import (
    InMemoryLock,
    RedisLock,
    get_lock,
    reset_for_test,
    set_lock,
)


class TestInMemoryLock:
    """单进程互斥。"""

    def test_acquire_then_release(self):
        lock = InMemoryLock()
        token = lock.try_acquire("k")
        assert token is not None
        assert lock.release("k", token) is True

    def test_acquire_twice_returns_none(self):
        lock = InMemoryLock()
        t1 = lock.try_acquire("k")
        t2 = lock.try_acquire("k")
        assert t1 is not None
        assert t2 is None

    def test_release_with_wrong_token_fails(self):
        lock = InMemoryLock()
        lock.try_acquire("k")
        assert lock.release("k", "wrong-token") is False

    def test_release_after_release_succeeds_again(self):
        lock = InMemoryLock()
        t1 = lock.try_acquire("k")
        lock.release("k", t1)
        t2 = lock.try_acquire("k")
        assert t2 is not None
        assert t2 != t1

    def test_different_keys_independent(self):
        lock = InMemoryLock()
        t1 = lock.try_acquire("a")
        t2 = lock.try_acquire("b")
        assert t1 is not None
        assert t2 is not None


class TestRedisLock:
    """Redis 锁（mock Redis 客户端）。"""

    def test_acquire_success(self):
        mock_client = MagicMock()
        mock_client.register_script.return_value = lambda **kw: lambda **kw2: 1
        mock_client.set.return_value = True
        with patch("redis.Redis.from_url", return_value=mock_client):
            lock = RedisLock("redis://localhost:6379/0")
            token = lock.try_acquire("k")
        assert token is not None
        mock_client.set.assert_called_once()

    def test_acquire_failure(self):
        mock_client = MagicMock()
        mock_client.register_script.return_value = lambda **kw: lambda **kw2: 1
        mock_client.set.return_value = None  # NX 失败
        with patch("redis.Redis.from_url", return_value=mock_client):
            lock = RedisLock("redis://localhost:6379/0")
            token = lock.try_acquire("k")
        assert token is None

    def test_release_uses_lua_script(self):
        mock_client = MagicMock()
        script = MagicMock(return_value=1)
        mock_client.register_script.return_value = script
        mock_client.set.return_value = True
        with patch("redis.Redis.from_url", return_value=mock_client):
            lock = RedisLock("redis://localhost:6379/0")
            token = lock.try_acquire("k")
            assert lock.release("k", token) is True
            script.assert_called_once()


class TestDefaultLock:
    """进程级默认。"""

    def test_get_lock_returns_inmemory(self):
        reset_for_test()
        l = get_lock()
        assert isinstance(l, InMemoryLock)

    def test_set_lock_overrides(self):
        reset_for_test()
        custom = InMemoryLock()
        set_lock(custom)
        assert get_lock() is custom

    def teardown_method(self):
        reset_for_test()
