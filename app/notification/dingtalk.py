"""钉钉通知通道（Mock + 真实接口占位）。

按 docs/design.md §3.2 通道协议扩展：
- name = 'dingtalk'
- send(recipient, subject, body) → SendResult

v3 范围：
- MockDingtalkChannel：测试 / 本地开发默认；
- DingtalkChannel：钉钉自定义机器人 webhook（access_token + secret 签名）。
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

import requests

from app.notification.base import Channel, SendResult

log = logging.getLogger(__name__)


class MockDingtalkChannel:
    """钉钉 Mock：与 MockChannel 同模式。"""

    name = "dingtalk"

    def __init__(self, *, fail_times: int = 0, retryable: bool = True) -> None:
        self._fail_times = fail_times
        self._retryable = retryable
        self._call_count = 0
        self.calls: list[tuple[str, str, str]] = []

    def send(self, recipient: str, subject: str, body: str) -> SendResult:
        self._call_count += 1
        self.calls.append((recipient, subject, body))
        if self._call_count <= self._fail_times:
            return SendResult(
                success=False,
                error=f"mock dingtalk failure {self._call_count}",
                retryable=self._retryable,
            )
        return SendResult(
            success=True, vendor_receipt_id=f"mock-dingtalk-{self._call_count}"
        )


class DingtalkChannel:
    """钉钉自定义机器人 webhook（官方文档）。

    Args:
        access_token: webhook URL 中的 access_token 部分
        secret: 加签密钥（启用加签时必填）
    """

    name = "dingtalk"

    def __init__(self, access_token: str, secret: Optional[str] = None) -> None:
        self.access_token = access_token
        self.secret = secret
        self._session = requests.Session()

    def _sign(self, timestamp: str) -> str:
        """计算钉钉加签。"""
        if not self.secret:
            return ""
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        import base64
        import urllib.parse
        return urllib.parse.quote_plus(base64.b64encode(hmac_code))

    def send(self, recipient: str, subject: str, body: str) -> SendResult:
        """recipient 必填（钉钉 at 列表）；subject 被丢弃（钉钉自定义机器人无主题）。"""
        try:
            url = f"https://oapi.dingtalk.com/robot/send?access_token={self.access_token}"
            timestamp = str(int(__import__("time").time() * 1000))
            if self.secret:
                url += f"&timestamp={timestamp}&sign={self._sign(timestamp)}"
            payload = {
                "msgtype": "text",
                "text": {"content": (subject + "\n" + body).strip() if subject else body},
                "at": {"atMobiles": [recipient] if recipient else [], "isAtAll": False},
            }
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") == 0:
                return SendResult(success=True, vendor_receipt_id=str(data.get("message_id", "")))
            err = data.get("errmsg") or data.get("errorMsg") or "unknown"
            return SendResult(success=False, error=err, retryable=False)
        except Exception as e:  # noqa: BLE001
            log.exception("dingtalk_send_failed")
            return SendResult(success=False, error=str(e), retryable=True)
