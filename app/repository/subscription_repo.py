"""Subscription 数据访问层。"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.tokens import InvalidToken, verify
from app.repository.models import Subscription
from app.repository.orm import SubscriptionStatus


def _new_uuid() -> str:
    return str(uuid.uuid4())


class SubscriptionRepository:
    """Subscription CRUD + 查询。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, sub_id: str) -> Optional[Subscription]:
        return self.session.get(Subscription, sub_id)

    def find_by_confirm_token(self, token: str) -> Optional[Subscription]:
        return self.session.execute(
            select(Subscription).where(Subscription.confirm_token == token)
        ).scalar_one_or_none()

    def find_by_cancel_token(self, token: str) -> Optional[Subscription]:
        return self.session.execute(
            select(Subscription).where(Subscription.cancel_token == token)
        ).scalar_one_or_none()

    def find_active_by_email(self, email: str) -> list[Subscription]:
        return list(
            self.session.execute(
                select(Subscription)
                .where(Subscription.email == email.lower())
                .where(Subscription.status == SubscriptionStatus.active)
            ).scalars().all()
        )

    def find_by_email(self, email: str) -> list[Subscription]:
        return list(
            self.session.execute(
                select(Subscription).where(Subscription.email == email.lower())
            ).scalars().all()
        )

    def insert_pending(
        self,
        *,
        exam_id: int,
        email: str,
        phone: str,
        reminder_level: str,
        channels: list[str],
        confirm_token: str,
        cancel_token: str,
    ) -> Subscription:
        sub = Subscription(
            id=_new_uuid(),
            exam_id=exam_id,
            email=email.lower(),
            phone=phone,
            reminder_level=reminder_level,
            channels=channels,
            status=SubscriptionStatus.pending,
            confirm_token=confirm_token,
            cancel_token=cancel_token,
        )
        self.session.add(sub)
        self.session.flush()
        return sub

    def mark_confirmed(self, sub: Subscription) -> None:
        from datetime import datetime

        sub.status = SubscriptionStatus.active
        sub.confirmed_at = datetime.utcnow()
        self.session.flush()

    def mark_cancelled(self, sub: Subscription) -> None:
        from datetime import datetime

        sub.status = SubscriptionStatus.cancelled
        sub.cancelled_at = datetime.utcnow()
        self.session.flush()


def verify_token_and_load(repo: SubscriptionRepository, token: str, *, action: str) -> Subscription:
    """解析 token 并加载对应订阅；action 不匹配或 token 失败抛 InvalidToken。"""
    try:
        payload = verify(token)
    except InvalidToken:
        raise
    if payload.get("action") != action:
        raise InvalidToken("action mismatch")
    sub_id = payload.get("sub_id")
    if not sub_id:
        raise InvalidToken("missing sub_id")
    sub = repo.get(sub_id)
    if sub is None:
        raise InvalidToken("subscription not found")
    # 额外检查 token 与记录一致（防 record 被删后 token 仍有效）
    if action == "confirm" and sub.confirm_token != token:
        raise InvalidToken("token mismatch")
    if action == "cancel" and sub.cancel_token != token:
        raise InvalidToken("token mismatch")
    return sub
