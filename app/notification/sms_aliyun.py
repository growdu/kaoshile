"""阿里云短信通道实现。

依赖 alibabacloud_dysmsapi20170525 + alibabacloud_tea_openapi。
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.notification.base import Channel, SendResult

log = logging.getLogger(__name__)


class SmsAliyunChannel:
    """阿里云短信。

    Args:
        access_key_id: 阿里云 AccessKeyId
        access_key_secret: 阿里云 AccessKeySecret
        sign_name: 阿里云已审核通过的短信签名
        template_code: 阿里云已审核通过的模板 ID
    """

    name = "sms_aliyun"

    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        sign_name: str,
        template_code: str,
    ) -> None:
        from alibabacloud_dysmsapi20170525.client import Client as SmsClient
        from alibabacloud_dysmsapi20170525 import models as sms_models
        from alibabacloud_tea_openapi import models as open_api_models

        cfg = open_api_models.Config(
            access_key_id=access_key_id, access_key_secret=access_key_secret
        )
        cfg.endpoint = "dysmsapi.aliyuncs.com"
        self.client = SmsClient(cfg)
        self._models = sms_models
        self.sign_name = sign_name
        self.template_code = template_code

    def send(
        self, recipient: str, subject: str, body: str
    ) -> SendResult:
        """发送短信。

        短信不接受 subject；body 作为模板参数 JSON 传入（key=content）。
        """
        try:
            req = self._models.SendSmsRequest(
                phone_numbers=recipient,
                sign_name=self.sign_name,
                template_code=self.template_code,
                template_param=json.dumps({"content": body}),
            )
            resp = self.client.send_sms(req)
            if resp.body.code == "OK":
                return SendResult(success=True, vendor_receipt_id=resp.body.request_id)
            err = resp.body.message or resp.body.code or "unknown"
            retryable = resp.body.code in {"isv.BUSINESS_LIMIT_CONTROL", "Throttling"}
            return SendResult(success=False, error=err, retryable=retryable)
        except Exception as e:  # noqa: BLE001
            log.exception("aliyun_sms_send_failed")
            return SendResult(success=False, error=str(e), retryable=True)


def build_from_settings() -> Optional[Channel]:
    from app.config import get_settings

    s = get_settings()
    if not s.aliyun_access_key_id or not s.aliyun_access_key_secret:
        return None
    if not s.aliyun_sms_sign_name or not s.aliyun_sms_template_code:
        return None
    return SmsAliyunChannel(
        access_key_id=s.aliyun_access_key_id,
        access_key_secret=s.aliyun_access_key_secret,
        sign_name=s.aliyun_sms_sign_name,
        template_code=s.aliyun_sms_template_code,
    )
