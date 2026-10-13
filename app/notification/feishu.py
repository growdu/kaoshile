"""飞书通知通道（Mock + 真实接口占位）。

按 docs/design.md §3.2 通道协议扩展：
- name = 'feishu'
- send(recipient, subject, body) → SendResult

v3 范围：
- MockFeishuChannel：测试 / 本地开发默认；
- FeishuChannel：飞书自定义机器人 webhook（access_token + secret 签名）。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
from typing import Optional

import requests

from app.notification.base import Channel, SendResult

log = logging.getLogger(__name__)


class MockFeishuChannel:
    """飞书 Mock。"""

    name = "feishu"

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
                error=f"mock feishu failure {self._call_count}",
                retryable=self._retryable,
            )
        return SendResult(
            success=True, vendor_receipt_id=f"mock-feishu-{self._call_count}"
        )


class FeishuChannel:
    """飞书自定义机器人 webhook（官方文档）。"""

    name = "feishu"

    def __init__(self, access_token: str, secret: Optional[str] = None) -> None:
        self.access_token = access_token
        self.secret = secret
        self._session = requests.Session()

    def _sign(self, timestamp: str) -> str:
        """飞书 HmacSHA256 加签。"""
        if not self.secret:
            return ""
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(hmac_code).decode()

    def send(self, recipient: str, subject: str, body: str) -> SendResult:
        """recipient 可选 at 用户 open_id；subject 飞书无对应概念被丢弃。"""
        try:
            timestamp = str(int(time.time()))
            url = (
                f"https://open.feishu.cn/open-apis/bot/v2/hook/{self.access_token}"
            )
            payload = {
                "timestamp": timestamp,
                "sign": self._sign(timestamp),
                "msg_type": "text",
                "content": {
                    "text": (subject + "\n" + body).strip() if subject else body
                },
            }
            resp = self._session.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("StatusCode") == 0 or data.get("code") == 0:
                return SendResult(success=True, vendor_receipt_id=str(data.get("data", {}).get("message_id", "")))
            err = data.get("msg") or "unknown"
            return SendResult(success=False, error=err, retryable=False)
        except Exception as e:  # noqa: BLE001
            log.exception("feishu_send_failed")
            return SendResult(success=False, error=str(e), retryable=True)
