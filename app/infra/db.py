"""数据库基础设施：SQLAlchemy engine + Session 工厂。

约定：
- engine 进程内单例（`get_engine()` 缓存）；
- SessionLocal 是 sessionmaker（非 scoped session，便于测试时显式关闭）；
- FastAPI 依赖 `get_db()` 用 yield 模式注入；
- 测试可调用 `reset_engine_for_test(url)` 重建（不同 URL）。

注意：M0 只建立基础设施；具体模型与迁移在 M1。
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _make_engine(database_url: str) -> Engine:
    """根据 URL 创建 engine。SQLite 需要 check_same_thread=False 以支持 FastAPI 依赖。"""
    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, connect_args=connect_args, future=True)


def get_engine() -> Engine:
    """返回进程内单例 engine。"""
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = _make_engine(settings.database_url)
        _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """返回 SessionLocal 工厂。"""
    if _session_factory is None:
        get_engine()  # 触发初始化
    assert _session_factory is not None
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：yield 一个 Session，正常时 commit，异常时 rollback。"""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_for_test(database_url: str) -> Engine:
    """测试钩子：丢弃单例并以新 URL 重建。

    接受具体 URL（通常是 sqlite:///:memory: 或 tempfile 路径）。
    """
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = _make_engine(database_url)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def init_db() -> None:
    """启动钩子：预热 engine，校验连接。"""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
