"""FastAPI 应用入口。

- `lifespan` 在启动时初始化日志与数据库；
- `/healthz` 始终返回 200（用于容器探针）；
- `/readyz` 在 db 连接就绪时返回 200（用于就绪探针）；
- 业务路由在 `app/api/public.py` 与 `app/api/manage.py`（后续里程碑挂载）。
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.api.manage import router as manage_router
from app.api.public import router as public_router
from app.config import get_settings
from app.infra.db import get_engine, init_db
from app.infra.logging import configure_logging, get_logger
from app.scheduler.scheduler import start_scheduler, stop_scheduler

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan：启动 / 关闭钩子。"""
    configure_logging()
    log.info("startup", version=__version__, app_env=get_settings().app_env)
    init_db()
    start_scheduler()
    log.info("startup_complete")
    yield
    stop_scheduler()
    log.info("shutdown")


def create_app() -> FastAPI:
    """工厂函数：方便测试构造独立实例并注入依赖覆盖。"""
    settings = get_settings()

    app = FastAPI(
        title="kaoshile",
        version=__version__,
        description="考试通知软件",
        lifespan=lifespan,
    )

    # ---------- 健康检查 ----------
    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, Any]:
        return {"ok": True, "data": {"status": "alive", "version": __version__}}

    @app.get("/readyz", tags=["meta"])
    def readyz() -> dict[str, Any]:
        try:
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:  # noqa: BLE001
            log.warning("readyz_failed", error=str(e))
            return {"ok": False, "error": {"code": "db_unavailable", "message": str(e)}}
        return {"ok": True, "data": {"status": "ready"}}

    # ---------- 元信息 ----------
    @app.get("/", tags=["meta"])
    def index() -> dict[str, Any]:
        return {
            "ok": True,
            "data": {
                "name": "kaoshile",
                "version": __version__,
                "app_env": settings.app_env,
                "docs": "/docs",
            },
        }

    # ---------- 业务路由 ----------
    app.include_router(public_router)
    app.include_router(manage_router)

    # ---------- 统一错误信封 ----------
    @app.exception_handler(HTTPException)
    async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        # 如果 detail 已经是信封形式，直接用；否则包装
        if isinstance(exc.detail, dict) and "ok" in exc.detail:
            payload = exc.detail
        else:
            payload = {
                "ok": False,
                "error": {"code": f"http_{exc.status_code}", "message": str(exc.detail)},
            }
        return JSONResponse(status_code=exc.status_code, content=payload)

    return app


# 进程级默认实例（uvicorn / 生产入口使用）
app = create_app()
