"""PII 清理 job：退订 7 天后清除邮箱 / 手机号。

约定：
- 每天跑一次；
- 仅清除 email / phone 字段；保留 subscription 主记录用于审计；
- cancel_token / confirm_token 一并清空（无法再退订或确认）；
- 触发时记 audit 日志。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.infra.logging import get_logger
from app.repository.models import Subscription
from app.repository.orm import SubscriptionStatus

log = get_logger(__name__)

RETENTION_DAYS = 7


def run(session_factory: Callable[[], Session]) -> int:
    """清理退订超过 RETENTION_DAYS 的订阅中的 PII。Returns: 清理数量。"""
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    count = 0
    with session_factory() as session:
        rows = list(
            session.execute(
                select(Subscription).where(
                    Subscription.status == SubscriptionStatus.cancelled,
                    Subscription.cancelled_at.is_not(None),
                    Subscription.cancelled_at < cutoff,
                )
            ).scalars().all()
        )
        for sub in rows:
            log.info(
                "pii_cleanup",
                subscription_id=sub.id,
                cancelled_at=sub.cancelled_at.isoformat() if sub.cancelled_at else None,
            )
            sub.email = ""
            sub.phone = ""
            sub.confirm_token = ""
            sub.cancel_token = ""
            count += 1
        session.commit()
    return count
