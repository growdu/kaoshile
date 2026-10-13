"""APScheduler 启动 / 关闭。

约定：
- 单进程内 AsyncIOScheduler，每分钟触发一次 scan_now；
- 测试可通过 disable() 完全跳过调度器。
"""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.infra.db import get_session_factory
from app.infra.logging import get_logger
from app.scheduler.node_scanner import scan_now
from app.scheduler.pii_cleanup import run as pii_run
from app.scheduler.verification_watchdog import run as watchdog_run

log = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    """启动调度器（幂等：已启动则不重启）。"""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(
        _scan_now_job,
        "cron",
        minute="*",
        id="node_scanner",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _watchdog_job,
        "cron",
        hour=3,
        minute=0,
        id="verification_watchdog",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        _pii_cleanup_job,
        "cron",
        hour=4,
        minute=0,
        id="pii_cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    log.info("scheduler_started")
    return _scheduler


def stop_scheduler() -> None:
    """关闭调度器。"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("scheduler_stopped")


def disable() -> None:
    """测试钩子：禁用启动调度器（让 lifespan 不真的拉起）。"""
    global _scheduler
    _scheduler = None


def _scan_now_job() -> None:
    """每分钟触发的 job 入口。"""
    try:
        session_factory = get_session_factory()
        triggered = scan_now(session_factory)
        if triggered:
            log.info("scan_triggered", count=triggered)
    except Exception:  # noqa: BLE001
        log.exception("scan_failed")


def _watchdog_job() -> None:
    """复核 watchdog：每天 03:00 跑一次。"""
    try:
        session_factory = get_session_factory()
        n = watchdog_run(session_factory)
        if n:
            log.warning("verification_watchdog_drafted", count=n)
    except Exception:  # noqa: BLE001
        log.exception("watchdog_failed")


def _pii_cleanup_job() -> None:
    """PII 清理：每天 04:00 跑一次。"""
    try:
        session_factory = get_session_factory()
        n = pii_run(session_factory)
        if n:
            log.info("pii_cleanup_done", count=n)
    except Exception:  # noqa: BLE001
        log.exception("pii_cleanup_failed")
