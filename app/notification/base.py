"""通知通道抽象：Channel Protocol + SendResult。

所有邮件 / 短信实现遵循同一接口，业务代码只依赖抽象。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class SendResult:
    """单次发送结果。

    Attributes:
        success: 是否成功
        vendor_receipt_id: 第三方回执 ID（用于审计）
        error: 失败原因（成功时为 None）
        retryable: 是否可重试（5xx / 网络错 / 限流 → True；4xx 参数错 → False）
    """

    success: bool
    vendor_receipt_id: str | None = None
    error: str | None = None
    retryable: bool = False

    def __bool__(self) -> bool:  # 允许 `if channel.send(...)` 直接判真
        return self.success


@runtime_checkable
class Channel(Protocol):
    """通知通道协议。

    实现可以是 EmailAliyun / SmsAliyun / Mock / 未来的微信、钉钉等。
    """

    name: str

    def send(self, recipient: str, subject: str, body: str) -> SendResult: ...
