"""Channel Protocol + SendResult 单元测试。"""
from __future__ import annotations

import pytest

from app.notification.base import Channel, SendResult


class TestSendResult:
    """SendResult 数据类。"""

    def test_default_failure(self):
        r = SendResult(success=False)
        assert r.success is False
        assert r.vendor_receipt_id is None
        assert r.error is None
        assert r.retryable is False
        assert not bool(r)

    def test_success_attributes(self):
        r = SendResult(success=True, vendor_receipt_id="abc123", retryable=False)
        assert r.success is True
        assert r.vendor_receipt_id == "abc123"
        assert bool(r)

    def test_retryable_flag(self):
        r = SendResult(success=False, error="timeout", retryable=True)
        assert r.retryable is True
        assert r.error == "timeout"

    def test_equality(self):
        a = SendResult(success=True, vendor_receipt_id="x")
        b = SendResult(success=True, vendor_receipt_id="x")
        c = SendResult(success=False, error="y")
        assert a == b
        assert a != c


class DummyChannel:
    """Protocol 的最小实现（用于静态检查）。"""

    name = "dummy"

    def send(self, recipient: str, subject: str, body: str) -> SendResult:
        return SendResult(success=True, vendor_receipt_id=f"d-{recipient}")


class TestChannelProtocol:
    """DummyChannel 实现 Protocol。"""

    def test_dummy_is_channel(self):
        ch: Channel = DummyChannel()
        assert ch.name == "dummy"
        r = ch.send("u@example.com", "subject", "body")
        assert r.success is True
        assert r.vendor_receipt_id == "d-u@example.com"

    def test_protocol_runtime_checkable(self):
        """Protocol 是 runtime_checkable，可以 isinstance。"""
        assert isinstance(DummyChannel(), Channel)
