"""阿里云通道单元测试（mock SDK 调用）。"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.notification.email_aliyun import EmailAliyunChannel
from app.notification.sms_aliyun import SmsAliyunChannel


@pytest.fixture
def email_channel() -> EmailAliyunChannel:
    return EmailAliyunChannel(
        access_key_id="id",
        access_key_secret="secret",
        region="cn-hangzhou",
        account_name="noreply@example.com",
        from_alias="kaoshile",
    )


@pytest.fixture
def sms_channel() -> SmsAliyunChannel:
    return SmsAliyunChannel(
        access_key_id="id",
        access_key_secret="secret",
        sign_name="考试通知",
        template_code="SMS_000",
    )


class TestEmailChannel:
    """EmailAliyunChannel。"""

    def test_name(self, email_channel):
        assert email_channel.name == "email_aliyun"

    def test_send_success(self, email_channel):
        """mock SDK 返回成功。"""
        with patch.object(email_channel, "client") as mock_client:
            mock_resp = type("R", (), {"body": type("B", (), {"request_id": "req-1"})()})()
            mock_client.single_send_mail.return_value = mock_resp
            r = email_channel.send("u@example.com", "subj", "body")
            assert r.success is True
            assert r.vendor_receipt_id == "req-1"
            mock_client.single_send_mail.assert_called_once()

    def test_send_failure_non_retryable(self, email_channel):
        """mock SDK 抛错且为参数错 → 非可重试。"""
        with patch.object(email_channel, "client") as mock_client:
            mock_client.single_send_mail.side_effect = Exception("InvalidAccountName")
            r = email_channel.send("u@example.com", "subj", "body")
            assert r.success is False
            assert "InvalidAccountName" in (r.error or "")
            assert r.retryable is False

    def test_send_failure_retryable(self, email_channel):
        """Throttling → 可重试。"""
        with patch.object(email_channel, "client") as mock_client:
            mock_client.single_send_mail.side_effect = Exception("Throttling.User")
            r = email_channel.send("u@example.com", "subj", "body")
            assert r.success is False
            assert r.retryable is True


class TestSmsChannel:
    """SmsAliyunChannel。"""

    def test_name(self, sms_channel):
        assert sms_channel.name == "sms_aliyun"

    def test_send_success(self, sms_channel):
        with patch.object(sms_channel, "client") as mock_client:
            mock_client.send_sms.return_value = type(
                "R",
                (),
                {"body": type("B", (), {"code": "OK", "request_id": "sms-1", "message": ""})()},
            )()
            r = sms_channel.send("13800138000", "", "body")
            assert r.success is True
            assert r.vendor_receipt_id == "sms-1"

    def test_send_failure(self, sms_channel):
        with patch.object(sms_channel, "client") as mock_client:
            mock_client.send_sms.return_value = type(
                "R",
                (),
                {"body": type("B", (), {"code": "isv.INVALID_PARAM", "request_id": "", "message": "bad"})()},
            )()
            r = sms_channel.send("13800138000", "", "body")
            assert r.success is False
            assert r.error is not None

    def test_send_failure_throttling_retryable(self, sms_channel):
        with patch.object(sms_channel, "client") as mock_client:
            mock_client.send_sms.return_value = type(
                "R",
                (),
                {"body": type("B", (), {"code": "isv.BUSINESS_LIMIT_CONTROL", "request_id": "", "message": "throttled"})()},
            )()
            r = sms_channel.send("13800138000", "", "body")
            assert r.success is False
            assert r.retryable is True

    def test_send_exception(self, sms_channel):
        with patch.object(sms_channel, "client") as mock_client:
            mock_client.send_sms.side_effect = Exception("network down")
            r = sms_channel.send("13800138000", "", "body")
            assert r.success is False
            assert r.retryable is True
