"""微信通知通道（Mock 实现 + 真实接口占位）。

按 docs/design.md §3.2 通道协议扩展：
- name = 'wechat'
- send(recipient, subject, body) → SendResult

v2 范围：
- 提供 MockWechatChannel 作为测试 / 本地开发默认；
- 提供 WechatChannel 真实接口占位（需 corp_id / corp_secret / agent_id 配置，未配置时抛 ImportError）。
"""
from __future__ import annotations

import logging
from typing import Optional

from app.notification.base import Channel, SendResult

log = logging.getLogger(__name__)


class MockWechatChannel:
    """微信 Mock：与 MockChannel 同样记录所有调用。"""

    name = "wechat"

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
                error=f"mock wechat failure {self._call_count}",
                retryable=self._retryable,
            )
        return SendResult(success=True, vendor_receipt_id=f"mock-wechat-{self._call_count}")


class WechatChannel:
    """微信真实通道占位：企业微信应用消息（access_token + 应用 ID）。

    依赖：requests（已在 dev）。
    v2 范围仅占位；正式接入需在阿里云 / 微信开放平台申请 corp_id / corp_secret。
    """

    name = "wechat"

    def __init__(self, corp_id: str, corp_secret: str, agent_id: str) -> None:
        import requests

        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.agent_id = agent_id
        self._session = requests.Session()
        self._token: Optional[str] = None

    def _get_token(self) -> str:
        """获取 access_token；v2 简化：每次现取，未缓存。"""
        url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        resp = self._session.get(
            url, params={"corpid": self.corp_id, "corpsecret": self.corp_secret}
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"wechat gettoken failed: {data}")
        self._token = data["access_token"]
        return self._token

    def send(self, recipient: str, subject: str, body: str) -> SendResult:
        """发送应用消息。

        微信应用消息 API：touser + msgtype='text'（v2 仅文本）；
        subject 在微信里无对应概念，被丢弃。
        """
        try:
            token = self._get_token()
            url = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
            resp = self._session.post(
                url,
                params={"access_token": token},
                json={
                    "touser": recipient,
                    "msgtype": "text",
                    "agentid": self.agent_id,
                    "text": {"content": body},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") == 0:
                return SendResult(success=True, vendor_receipt_id=str(data.get("msgid", "")))
            return SendResult(
                success=False,
                error=data.get("errmsg", "unknown"),
                retryable=False,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("wechat_send_failed")
            return SendResult(success=False, error=str(e), retryable=True)
