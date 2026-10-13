"""通知用例：检查幂等、调 channel、重试、写 NotificationLog。

约定：
- 同一 (sub, node, channel) 仅首次写 NotificationLog；
- 失败按指数退避重试（最多 max_attempts 次）；
- 重试间隔 1s / 5s / 25s。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Protocol

from app.infra.logging import get_logger
from app.notification.base import Channel, SendResult
from app.notification.registry import get as registry_get
from app.repository.models import Subscription
from app.repository.notification_log_repo import NotificationLogRepository
from app.repository.orm import NodeType, NotificationChannel, NotificationStatus

log = get_logger(__name__)

RETRY_DELAYS = (1, 5, 25)  # 指数退避


class NotificationError(Exception):
    """通知发送失败（最终失败）。"""


@dataclass
class NotificationService:
    """通知发送用例：幂等检查 + 重试 + 写 log。"""

    log_repo: NotificationLogRepository

    def send_one_off(
        self,
        subscription_or_email,
        *,
        subject: str,
        body: str,
    ) -> list[str]:
        """一次性通知（不写 NotificationLog）。

        Args:
            subscription_or_email: Subscription 对象 → 走其 channels + email/phone；
                                或 str → 视为 email，单通道 email。
        """
        from app.repository.models import Subscription as Sub  # noqa: PLC0415

        if isinstance(subscription_or_email, Sub):
            sub = subscription_or_email
            channels = sub.channels
            email = sub.email
            phone = sub.phone
        else:
            channels = ["email"]
            email = str(subscription_or_email)
            phone = ""

        errors: list[str] = []
        for ch_name in channels:
            try:
                channel = registry_get(ch_name)
            except KeyError:
                errors.append(f"channel {ch_name!r} not registered")
                continue
            recipient = email if ch_name == "email" else phone
            try:
                result = channel.send(recipient, subject, body)
                if not result.success:
                    errors.append(f"{ch_name}: {result.error or 'unknown'}")
            except Exception as e:  # noqa: BLE001
                log.exception("notification_send_failed", extra={"channel": ch_name})
                errors.append(f"{ch_name}: exception {e!s}")
        return errors

    @property
    def channels(self) -> dict[str, Channel]:
        """所有已注册通道。"""
        from app.notification.registry import get_all

        return get_all()

    def dispatch(
        self,
        subscription: Subscription,
        *,
        node_type: NodeType,
        exam_id: int,
        subject: str,
        body: str,
        max_attempts: int = 3,
    ) -> bool:
        """为每个订阅通道发送一次通知。

        Returns:
            True if 全部成功；False if 任一失败（含重试全失败）。
        """
        all_ok = True
        for ch_name in subscription.channels:
            ok = self._dispatch_one(
                subscription,
                channel_name=ch_name,
                node_type=node_type,
                exam_id=exam_id,
                subject=subject,
                body=body,
                max_attempts=max_attempts,
            )
            if not ok:
                all_ok = False
        return all_ok

    def _dispatch_one(
        self,
        subscription: Subscription,
        *,
        channel_name: str,
        node_type: NodeType,
        exam_id: int,
        subject: str,
        body: str,
        max_attempts: int,
    ) -> bool:
        channel_enum = NotificationChannel(channel_name)
        # 幂等：已存在则跳过
        if self.log_repo.exists(
            subscription_id=subscription.id,
            node_type=node_type,
            channel=channel_enum,
        ):
            log.info(
                "notification_skip_existing",
                subscription_id=subscription.id,
                node_type=node_type.value,
                channel=channel_name,
            )
            return True

        log_row = self.log_repo.insert_queued(
            subscription_id=subscription.id,
            exam_id=exam_id,
            node_type=node_type,
            channel=channel_enum,
        )

        try:
            channel = registry_get(channel_name)
        except KeyError as e:
            self.log_repo.mark_failed(log_row, error=f"channel not registered: {e}")
            return False

        recipient = subscription.email if channel_name == "email" else subscription.phone
        last_error: str | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                result: SendResult = channel.send(recipient, subject, body)
            except Exception as e:  # noqa: BLE001
                last_error = f"exception: {e!s}"
                log.exception(
                    "notification_send_exception",
                    attempt=attempt,
                    channel=channel_name,
                )
            else:
                if result.success:
                    self.log_repo.mark_sent(log_row, receipt_id=result.vendor_receipt_id or "")
                    return True
                last_error = result.error or "unknown"
                if not result.retryable:
                    break
            # 退避
            if attempt < max_attempts:
                time.sleep(RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)])

        self.log_repo.mark_failed(log_row, error=last_error or "exhausted retries")
        return False


class _LoggerProtocol(Protocol):
    def info(self, msg: str, *args: object, **kwargs: object) -> None: ...
    def exception(self, msg: str, *args: object, **kwargs: object) -> None: ...
