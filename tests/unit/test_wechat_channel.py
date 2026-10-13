"""微信通知通道单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.notification.wechat import MockWechatChannel, WechatChannel


class TestMockWechatChannel:
    """Mock 行为。"""

    def test_name(self):
        assert MockWechatChannel().name == "wechat"

    def test_send_success(self):
        ch = MockWechatChannel()
        r = ch.send("userid", "subj", "body")
        assert r.success is True
        assert r.vendor_receipt_id == "mock-wechat-1"

    def test_records_calls(self):
        ch = MockWechatChannel()
        ch.send("u1", "s", "b1")
        ch.send("u2", "s", "b2")
        assert ch._call_count == 2
        assert ch.calls[0][0] == "u1"

    def test_fail_then_succeed(self):
        ch = MockWechatChannel(fail_times=1)
        r1 = ch.send("u", "s", "b")
        r2 = ch.send("u", "s", "b")
        assert r1.success is False
        assert r2.success is True


class TestWechatChannel:
    """真实通道占位。"""

    def test_name(self):
        ch = WechatChannel(corp_id="cid", corp_secret="sec", agent_id="aid")
        assert ch.name == "wechat"

    def test_send_success(self):
        ch = WechatChannel(corp_id="cid", corp_secret="sec", agent_id="aid")
        # mock session：token 调用 + 发送调用
        token_resp = MagicMock(
            json=lambda: {"errcode": 0, "access_token": "T"}
        )
        token_resp.raise_for_status = lambda: None
        send_resp = MagicMock(
            json=lambda: {"errcode": 0, "msgid": "msg-123"}
        )
        send_resp.raise_for_status = lambda: None

        with patch.object(ch._session, "get", return_value=token_resp):
            with patch.object(ch._session, "post", return_value=send_resp):
                r = ch.send("userid", "subj", "body")
        assert r.success is True
        assert r.vendor_receipt_id == "msg-123"

    def test_send_api_error(self):
        ch = WechatChannel(corp_id="cid", corp_secret="sec", agent_id="aid")
        token_resp = MagicMock(
            json=lambda: {"errcode": 0, "access_token": "T"}
        )
        token_resp.raise_for_status = lambda: None
        send_resp = MagicMock(
            json=lambda: {"errcode": 40001, "errmsg": "invalid credential"}
        )
        send_resp.raise_for_status = lambda: None

        with patch.object(ch._session, "get", return_value=token_resp):
            with patch.object(ch._session, "post", return_value=send_resp):
                r = ch.send("userid", "subj", "body")
        assert r.success is False
        assert "invalid credential" in (r.error or "")
        assert r.retryable is False

    def test_send_network_exception(self):
        ch = WechatChannel(corp_id="cid", corp_secret="sec", agent_id="aid")
        with patch.object(ch._session, "get", side_effect=Exception("timeout")):
            r = ch.send("userid", "subj", "body")
        assert r.success is False
        assert r.retryable is True
