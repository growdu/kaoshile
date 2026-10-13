"""钉钉 + 飞书通知通道单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.notification.dingtalk import DingtalkChannel, MockDingtalkChannel
from app.notification.feishu import FeishuChannel, MockFeishuChannel


class TestMockDingtalk:
    def test_name(self):
        assert MockDingtalkChannel().name == "dingtalk"

    def test_send_success(self):
        ch = MockDingtalkChannel()
        r = ch.send("13800138000", "subj", "body")
        assert r.success is True
        assert r.vendor_receipt_id == "mock-dingtalk-1"

    def test_fail_then_succeed(self):
        ch = MockDingtalkChannel(fail_times=1)
        assert ch.send("u", "s", "b").success is False
        assert ch.send("u", "s", "b").success is True


class TestDingtalkChannel:
    def test_name(self):
        ch = DingtalkChannel(access_token="tok")
        assert ch.name == "dingtalk"

    def test_send_success(self):
        ch = DingtalkChannel(access_token="tok", secret=None)
        resp = MagicMock()
        resp.raise_for_status = lambda: None
        resp.json = lambda: {"errcode": 0, "message_id": "m1"}
        with patch.object(ch._session, "post", return_value=resp):
            r = ch.send("13800138000", "subj", "body")
        assert r.success is True
        assert r.vendor_receipt_id == "m1"

    def test_send_with_secret_signs(self):
        ch = DingtalkChannel(access_token="tok", secret="SEC")
        resp = MagicMock()
        resp.raise_for_status = lambda: None
        resp.json = lambda: {"errcode": 0, "message_id": "m2"}
        with patch.object(ch._session, "post", return_value=resp) as mock_post:
            r = ch.send("u", "s", "b")
        assert r.success is True
        # url 应含 sign=...
        called_url = mock_post.call_args[0][0]
        assert "sign=" in called_url

    def test_send_api_error(self):
        ch = DingtalkChannel(access_token="tok")
        resp = MagicMock()
        resp.raise_for_status = lambda: None
        resp.json = lambda: {"errcode": 310000, "errmsg": "bad token"}
        with patch.object(ch._session, "post", return_value=resp):
            r = ch.send("u", "s", "b")
        assert r.success is False
        assert r.retryable is False

    def test_send_exception(self):
        ch = DingtalkChannel(access_token="tok")
        with patch.object(ch._session, "post", side_effect=Exception("timeout")):
            r = ch.send("u", "s", "b")
        assert r.success is False
        assert r.retryable is True


class TestMockFeishu:
    def test_name(self):
        assert MockFeishuChannel().name == "feishu"

    def test_send_success(self):
        ch = MockFeishuChannel()
        r = ch.send("ou_xxx", "subj", "body")
        assert r.success is True

    def test_fail_then_succeed(self):
        ch = MockFeishuChannel(fail_times=2)
        assert ch.send("u", "s", "b").success is False
        assert ch.send("u", "s", "b").success is False
        assert ch.send("u", "s", "b").success is True


class TestFeishuChannel:
    def test_name(self):
        ch = FeishuChannel(access_token="tok")
        assert ch.name == "feishu"

    def test_send_success(self):
        ch = FeishuChannel(access_token="tok", secret="SEC")
        resp = MagicMock()
        resp.raise_for_status = lambda: None
        resp.json = lambda: {"StatusCode": 0, "data": {"message_id": "m1"}}
        with patch.object(ch._session, "post", return_value=resp) as mock_post:
            r = ch.send("ou_xxx", "subj", "body")
        assert r.success is True
        # payload 应含 timestamp + sign
        payload = mock_post.call_args[1]["json"]
        assert "timestamp" in payload
        assert "sign" in payload

    def test_send_api_error(self):
        ch = FeishuChannel(access_token="tok")
        resp = MagicMock()
        resp.raise_for_status = lambda: None
        resp.json = lambda: {"StatusCode": 230002, "msg": "no permission"}
        with patch.object(ch._session, "post", return_value=resp):
            r = ch.send("u", "s", "b")
        assert r.success is False
        assert r.retryable is False

    def test_send_exception(self):
        ch = FeishuChannel(access_token="tok")
        with patch.object(ch._session, "post", side_effect=Exception("net err")):
            r = ch.send("u", "s", "b")
        assert r.retryable is True
