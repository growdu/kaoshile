"""节点扫描：每分钟找出该触发的 (订阅, 节点, 通道) 三元组。

约定：
- 调用方提供 session factory（不绑 db 引擎，方便测试注入）；
- 当前时间用 Asia/Shanghai；
- 对每个 active 订阅，按 reminder_level 推导其所有触发时刻，
  若任一触发时刻落在 [now - WINDOW, now] 区间内 → 视为该节点到期，
  调 NotificationService.dispatch；
- 幂等由 NotificationLogRepo.exists 保证。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.domain.reminder_policy import compute_send_times
from app.infra.logging import get_logger
from app.infra.time import now_shanghai
from app.repository.models import Subscription
from app.repository.notification_log_repo import NotificationLogRepository
from app.repository.orm import SubscriptionStatus
from app.scheduler.distributed_lock import get_lock
from app.usecase.notification import NotificationService

log = get_logger(__name__)

# 扫描窗口：每分钟跑一次，扫 [now - WINDOW, now]
WINDOW = timedelta(minutes=1)


def scan_now(
    session_factory: Callable[[], Session],
    *,
    notification_service_factory: Callable[[NotificationLogRepository], NotificationService]
    | None = None,
    lock=None,
) -> int:
    """扫描并触发现有通知。

    Returns:
        触发的 (订阅, 节点, 通道) 三元组数量。
    """
    # 多实例安全：默认通过分布式锁保证每窗口只跑一个实例
    lock = lock or get_lock()
    token = lock.try_acquire("node_scanner", ttl_seconds=120)
    if token is None:
        log.info("scan_skipped_lock_held")
        return 0
    try:
        return _scan_now_unlocked(
            session_factory, notification_service_factory=notification_service_factory
        )
    finally:
        lock.release("node_scanner", token)


def _scan_now_unlocked(
    session_factory: Callable[[], Session],
    *,
    notification_service_factory: Callable[[NotificationLogRepository], NotificationService]
    | None = None,
) -> int:
    now = now_shanghai()
    window_start = now - WINDOW
    triggered = 0

    with session_factory() as session:
        # 1. 找出所有 active 订阅
        active_subs = list(
            session.execute(
                select(Subscription).where(Subscription.status == SubscriptionStatus.active)
            ).scalars().all()
        )
        log_repo = NotificationLogRepository(session)
        if notification_service_factory is None:
            notification_service_factory = lambda r: NotificationService(log_repo=r)
        notif_svc = notification_service_factory(log_repo)

        for sub in active_subs:
            exam = sub.exam  # relationship
            if exam is None:
                continue
            send_times = compute_send_times(exam, sub.reminder_level)
            for node_type, times in send_times.items():
                # 该节点是否需要触发（任一时刻落在窗口内）
                if not any(window_start <= t <= now for t in times):
                    continue
                # 构造 subject / body（v1 简化文本）
                node_label = {
                    "registration_start": "报名开始",
                    "registration_end": "报名截止",
                    "payment_end": "缴费截止",
                    "admission_start": "准考证打印开始",
                    "exam_day": "考试日",
                }.get(node_type, node_type)
                subject = f"【{exam.name}】{node_label}提醒"
                # 取窗口内的最近触发时刻
                triggered_times = [t for t in times if window_start <= t <= now]
                base = triggered_times[-1] if triggered_times else now
                body_lines = [
                    f"考试：{exam.name}",
                    f"类别：{exam.category}",
                    f"主办：{exam.organizer or '未提供'}",
                    f"节点：{node_label}",
                    f"时间：{base.isoformat()}",
                    "",
                    f"官方公告：{exam.official_url or exam.source_url}",
                    f"取消订阅：/s/{sub.cancel_token}",
                ]
                body = "\n".join(body_lines)

                if notif_svc.dispatch(
                    sub,
                    node_type=_node_enum(node_type),
                    exam_id=exam.id,
                    subject=subject,
                    body=body,
                ):
                    triggered += len(sub.channels)
            session.commit()
    return triggered


def _node_enum(name: str):
    """字符串 → NodeType 枚举。"""
    from app.repository.orm import NodeType

    return NodeType(name)
