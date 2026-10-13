"""MockChannel：测试与本地开发用的假通道。

记录所有调用，可配置失败次数（fail_times）模拟瞬时错误。
永远不连真实网络。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.notification.base import Channel, SendResult


@dataclass
class CallRecord:
    """单次 send 调用的记录。"""

    recipient: str
    subject: str
    body: str


class MockChannel:
    """Mock 通道。

    Args:
        name: 通道名（用于多通道区分）
        fail_times: 前 N 次调用返回失败；之后返回成功
        retryable: 失败时是否标记 retryable
        latency_seconds: 模拟网络延迟（默认 0）
    """

    def __init__(
        self,
        name: str = "mock",
        *,
        fail_times: int = 0,
        retryable: bool = True,
    ) -> None:
        self.name = name
        self._fail_times = fail_times
        self._retryable = retryable
        self.calls: list[CallRecord] = []
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def send(self, recipient: str, subject: str, body: str) -> SendResult:
        self._call_count += 1
        self.calls.append(CallRecord(recipient=recipient, subject=subject, body=body))
        if self._call_count <= self._fail_times:
            return SendResult(
                success=False,
                error=f"mock transient failure ({self._call_count}/{self._fail_times})",
                retryable=self._retryable,
            )
        return SendResult(
            success=True,
            vendor_receipt_id=f"mock-{self.name}-{self._call_count}",
        )

    # ---- 测试便捷方法 ----

    def reset(self) -> None:
        self.calls.clear()
        self._call_count = 0
        self._fail_times = 0


def build_mock_channels() -> dict[str, Channel]:
    """构造一组默认 mock 通道（email + sms）。"""
    return {
        "email": MockChannel("email"),
        "sms": MockChannel("sms"),
    }
