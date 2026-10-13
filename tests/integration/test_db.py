"""db 基础设施集成测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.infra.db import (
    get_db,
    get_engine,
    get_session_factory,
    init_db,
    reset_engine_for_test,
)


@pytest.fixture
def in_memory_engine() -> Engine:
    """把全局 engine 切到内存 SQLite。"""
    reset_engine_for_test("sqlite:///:memory:")
    yield get_engine()


class TestEngine:
    """engine 单例与切换。"""

    def test_engine_singleton(self, in_memory_engine):
        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2
        assert e1 is in_memory_engine

    def test_reset_engine_for_test(self):
        reset_engine_for_test("sqlite:///:memory:")
        e1 = get_engine()
        reset_engine_for_test("sqlite:///:memory:")
        e2 = get_engine()
        assert e1 is not e2

    def test_sqlite_url(self, in_memory_engine):
        url = str(in_memory_engine.url)
        assert url.startswith("sqlite")


class TestSessionFactory:
    """session 工厂。"""

    def test_factory_callable(self, in_memory_engine):
        factory = get_session_factory()
        assert factory is not None

    def test_open_and_close_session(self, in_memory_engine):
        factory = get_session_factory()
        s = factory()
        try:
            assert isinstance(s, Session)
        finally:
            s.close()

    def test_session_can_execute_sql(self, in_memory_engine):
        factory = get_session_factory()
        s = factory()
        try:
            result = s.execute(text("SELECT 1 + 1")).scalar()
            assert result == 2
        finally:
            s.close()


class TestGetDb:
    """FastAPI 依赖 yield Session。"""

    def test_yields_session_and_closes(self, in_memory_engine):
        gen = get_db()
        s = next(gen)
        assert isinstance(s, Session)
        # 正常退出 generator → 触发 finally 关闭
        with pytest.raises(StopIteration):
            next(gen)

    def test_rollback_on_exception(self, in_memory_engine):
        gen = get_db()
        s = next(gen)
        # 让事务脏
        s.execute(text("CREATE TABLE t (x INT)"))
        s.execute(text("INSERT INTO t VALUES (1)"))
        # throw 异常 → generator 内部 except → rollback → finally 关闭
        with pytest.raises(RuntimeError):
            gen.throw(RuntimeError("boom"))
        with pytest.raises(StopIteration):
            next(gen)


class TestInitDb:
    """init_db 健康检查。"""

    def test_init_db_connects(self, in_memory_engine):
        init_db()  # 不抛异常即可
