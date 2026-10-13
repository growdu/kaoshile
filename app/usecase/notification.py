"""通知用例：根据订阅通道 + 模板生成内容并通过对应 Channel 发送。

v1 简化：
- 邮件模板极简（subject + body）；
- 短信通过 SmsChannel 发送；
- 不做模板系统（M11 才完整实现）；
- 失败重试在 M7 调度器中处理（M7 之前同步失败仅记日志）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Protocol

from app.notification.base import Channel
from app.notification.registry import get as registry_get
from app.repository.models import Subscription

log = logging.getLogger(__name__)


@dataclass
class NotificationService:
    """通知发送器：按 subscription.channels 选择通道并发送。"""

    notifier: Optional["LoggerLike"] = None

    def dispatch(
        self,
        subscription: Subscription,
        *,
        subject: str,
        body: str,
    ) -> list[str]:
        """同步发送所有勾选通道；返回发送失败的错误列表（成功返回空）。"""
        errors: list[str] = []
        for channel_name in subscription.channels:
            try:
                channel = registry_get(channel_name)
            except KeyError:
                errors.append(f"channel {channel_name!r} not registered")
                continue
            recipient = subscription.email if channel_name == "email" else subscription.phone
            try:
                result = channel.send(recipient, subject, body)
                if not result.success:
                    errors.append(f"{channel_name}: {result.error or 'unknown'}")
            except Exception as e:  # noqa: BLE001
                log.exception("notification_send_failed", extra={"channel": channel_name})
                errors.append(f"{channel_name}: exception {e!s}")
        return errors


class LoggerLike(Protocol):
    def info(self, msg: str, *args: object) -> None: ...
    def exception(self, msg: str, *args: object) -> None: ...
