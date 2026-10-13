"""订阅业务用例：创建 / 确认 / 退订 / 查询。

约定：
- 不直接 import ORM，由 repository 注入；
- token 生成走 app.domain.tokens；
- 通知发送通过 NotificationService（注入）；
- 校验邮箱格式、phone 格式、channel 与 level 合法。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Protocol

from app.domain.reminder_policy import VALID_LEVELS, compute_send_times
from app.domain.tokens import sign
from app.repository.exam_repo import ExamRepository
from app.repository.models import Exam, Subscription
from app.repository.orm import ExamStatus, SubscriptionStatus
from app.repository.subscription_repo import SubscriptionRepository

VALID_CHANNELS = frozenset({"email", "sms"})
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\d{11}$")


class NotificationDispatcher(Protocol):
    """通知发送抽象。"""

    def dispatch(self, subscription: Subscription, *, subject: str, body: str) -> None: ...


class SubscriptionError(Exception):
    """业务校验错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_inputs(
    email: str,
    phone: str,
    level: str,
    channels: list[str],
) -> None:
    if not EMAIL_RE.match(email):
        raise SubscriptionError("invalid_email", "邮箱格式不正确")
    if not PHONE_RE.match(phone):
        raise SubscriptionError("invalid_phone", "手机号必须为 11 位数字")
    if level not in VALID_LEVELS:
        raise SubscriptionError("invalid_level", f"提醒档位必须是 {sorted(VALID_LEVELS)}")
    if not channels:
        raise SubscriptionError("no_channels", "至少选择一个通知通道")
    bad = [c for c in channels if c not in VALID_CHANNELS]
    if bad:
        raise SubscriptionError("invalid_channels", f"未知通道：{bad}")


class SubscriptionService:
    """编排：考试查询 / 校验 / token 签发 / 入库 / 通知。"""

    def __init__(
        self,
        exam_repo: ExamRepository,
        sub_repo: SubscriptionRepository,
        notifier: NotificationDispatcher | None = None,
    ) -> None:
        self.exam_repo = exam_repo
        self.sub_repo = sub_repo
        self.notifier = notifier

    def create(
        self,
        *,
        exam_id: int,
        email: str,
        phone: str,
        level: str,
        channels: list[str],
    ) -> tuple[Subscription, Exam, dict[str, list[datetime]]]:
        """创建 pending 订阅，发送确认通知，返回 (sub, exam, send_times)。

        Raises:
            SubscriptionError: 校验失败或考试不可订阅。
        """
        validate_inputs(email, phone, level, channels)

        exam = self.exam_repo.get(exam_id)
        if exam is None:
            raise SubscriptionError("exam_not_found", f"考试 {exam_id} 不存在")
        if exam.status != ExamStatus.open:
            raise SubscriptionError("exam_not_open", f"考试 {exam_id} 未开放订阅")

        # 防重复 active 订阅
        existing_active = [
            s for s in self.sub_repo.find_active_by_email(email.lower()) if s.exam_id == exam_id
        ]
        if existing_active:
            raise SubscriptionError(
                "already_subscribed", "该邮箱已订阅此考试"
            )

        # token
        # sub_id 先用占位 uuid，签 token 后再覆盖
        placeholder_id = "placeholder"
        confirm_token = sign(
            {"sub_id": placeholder_id, "action": "confirm"},
            ttl_days=30,
        )
        cancel_token = sign(
            {"sub_id": placeholder_id, "action": "cancel"},
            ttl_days=30,
        )

        sub = self.sub_repo.insert_pending(
            exam_id=exam_id,
            email=email,
            phone=phone,
            reminder_level=level,
            channels=channels,
            confirm_token=confirm_token,
            cancel_token=cancel_token,
        )

        # 重新签发带真实 sub_id 的 token 并覆盖
        real_confirm = sign({"sub_id": sub.id, "action": "confirm"}, ttl_days=30)
        real_cancel = sign({"sub_id": sub.id, "action": "cancel"}, ttl_days=30)
        sub.confirm_token = real_confirm
        sub.cancel_token = real_cancel
        self.sub_repo.session.flush()

        # 计算 send_times
        send_times = compute_send_times(exam, level)

        # 通知（v1 同步发送；M7 调度器启用后可改为 enqueue）
        if self.notifier is not None:
            self.notifier.send_one_off(
                sub,
                subject=f"请确认订阅：{exam.name}",
                body=(
                    f"感谢订阅【{exam.name}】。\n"
                    f"点击确认：/c/{real_confirm}\n"
                    f"取消订阅：/s/{real_cancel}"
                ),
            )

        return sub, exam, send_times

    def confirm(self, token: str) -> Subscription:
        """确认订阅：pending → active。

        Raises:
            InvalidToken / SubscriptionError.
        """
        from app.repository.subscription_repo import verify_token_and_load

        sub = verify_token_and_load(self.sub_repo, token, action="confirm")
        if sub.status == SubscriptionStatus.cancelled:
            raise SubscriptionError("already_cancelled", "订阅已退订，无法确认")
        if sub.status == SubscriptionStatus.active:
            return sub  # 幂等
        self.sub_repo.mark_confirmed(sub)
        return sub

    def cancel(self, token: str) -> Subscription:
        """退订：active / pending → cancelled。

        Raises:
            InvalidToken / SubscriptionError.
        """
        from app.repository.subscription_repo import verify_token_and_load

        sub = verify_token_and_load(self.sub_repo, token, action="cancel")
        if sub.status == SubscriptionStatus.cancelled:
            return sub  # 幂等
        self.sub_repo.mark_cancelled(sub)
        return sub

    def list_for_email(self, email: str) -> list[Subscription]:
        """列出邮箱下所有订阅。"""
        return self.sub_repo.find_by_email(email)
