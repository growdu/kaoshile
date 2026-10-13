"""测试全局 fixture 与配置。

按实现方案 §11.1，每个里程碑添加 fixture 在此。
"""
import os

import pytest

# 在导入 app 之前把测试环境变量设好，避免 pydantic-settings 读到宿主机 .env
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LINK_SECRET", "test-secret-must-be-32-bytes-or-more-for-hs256")
os.environ.setdefault("MANAGE_PASSWORD_HASH", "$2b$12$dummyhashplaceholderfortests....")


@pytest.fixture(autouse=True)
def _reset_module_globals():
    """每个测试后清理模块级单例状态，避免跨测试污染。"""
    import structlog

    import app.infra.db as db_mod
    from app.notification import registry
    from app.scheduler import scheduler as sched_mod

    yield
    # 还原 engine、registry、scheduler、structlog
    if db_mod._engine is not None:
        try:
            db_mod._engine.dispose()
        except Exception:
            pass
    db_mod._engine = None
    db_mod._session_factory = None
    registry.reset_for_test()
    if sched_mod._scheduler is not None:
        sched_mod._scheduler.shutdown(wait=False)
        sched_mod._scheduler = None
    # 重置 structlog，避免上次 capsys 收尾导致 file closed
    structlog.reset_defaults()
