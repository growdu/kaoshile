"""MockChannel + registry 单元测试。"""
from __future__ import annotations

import pytest

from app.notification.base import Channel, SendResult
from app.notification.mock import MockChannel, build_mock_channels
from app.notification.registry import get, get_all, register, reset_for_test


class TestMockChannelHappy:
    """默认行为。"""

    def test_first_call_succeeds(self):
        ch = MockChannel()
        r = ch.send("u@example.com", "subj", "body")
        assert r.success is True
        assert r.vendor_receipt_id is not None

    def test_records_call(self):
        ch = MockChannel()
        ch.send("u@example.com", "subj", "body 1")
        ch.send("v@example.com", "subj2", "body 2")
        assert ch.call_count == 2
        assert ch.calls[0].recipient == "u@example.com"
        assert ch.calls[1].body == "body 2"

    def test_receipt_ids_increment(self):
        ch = MockChannel()
        r1 = ch.send("u", "s", "b")
        r2 = ch.send("u", "s", "b")
        assert r1.vendor_receipt_id == "mock-mock-1"
        assert r2.vendor_receipt_id == "mock-mock-2"


class TestMockChannelFailures:
    """失败注入。"""

    def test_fail_times_2_fails_first_two(self):
        ch = MockChannel(fail_times=2)
        r1 = ch.send("u", "s", "b")
        r2 = ch.send("u", "s", "b")
        r3 = ch.send("u", "s", "b")
        assert r1.success is False
        assert r2.success is False
        assert r3.success is True
        assert r1.retryable is True
        assert r1.error is not None

    def test_retryable_false(self):
        ch = MockChannel(fail_times=1, retryable=False)
        r = ch.send("u", "s", "b")
        assert r.success is False
        assert r.retryable is False

    def test_all_calls_fail(self):
        ch = MockChannel(fail_times=100)
        for _ in range(5):
            r = ch.send("u", "s", "b")
            assert r.success is False


class TestBuildMockChannels:
    """工厂。"""

    def test_returns_email_and_sms(self):
        channels = build_mock_channels()
        assert set(channels.keys()) == {"email", "sms"}
        for ch in channels.values():
            assert isinstance(ch, Channel)


class TestRegistry:
    """通道注册表。"""

    def setup_method(self):
        reset_for_test()

    def test_register_and_get(self):
        ch = MockChannel("email")
        register(ch)
        assert get("email") is ch

    def test_register_overwrites(self):
        ch1 = MockChannel("email")
        ch2 = MockChannel("email")
        register(ch1)
        register(ch2)
        assert get("email") is ch2

    def test_get_missing_raises(self):
        with pytest.raises(KeyError):
            get("nonexistent")

    def test_get_all_returns_copy(self):
        ch = MockChannel("email")
        register(ch)
        all_channels = get_all()
        all_channels["email"] = MockChannel("other")  # 不应影响 registry
        assert get("email") is ch

    def test_reset_clears(self):
        register(MockChannel("email"))
        register(MockChannel("sms"))
        reset_for_test()
        assert get_all() == {}
