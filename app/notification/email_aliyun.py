"""阿里云邮件推送（DirectMail）通道实现。

依赖 alibabacloud_dm20151123 + alibabacloud_tea_openapi（optional aliyun）。
未安装 SDK 时构造失败（ImportError），由调用方决定是否回退到 Mock。
"""
from __future__ import annotations

import logging
from typing import Optional

from app.notification.base import Channel, SendResult

log = logging.getLogger(__name__)


class EmailAliyunChannel:
    """阿里云邮件邮件（DM）。

    Args:
        access_key_id: 阿里云 AccessKeyId
        access_key_secret: 阿里云 AccessKeySecret
        region: 如 'cn-hangzhou'
        account_name: 发件邮箱
        from_alias: 发件人显示名
    """

    name = "email_aliyun"

    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        region: str,
        account_name: str,
        from_alias: str,
    ) -> None:
        from alibabacloud_dm20151123.client import Client as DmClient
        from alibabacloud_dm20151123 import models as dm_models
        from alibabacloud_tea_openapi import models as open_api_models

        cfg = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            region_id=region,
        )
        cfg.endpoint = f"dm.{region}.aliyuncs.com"
        self.client = DmClient(cfg)
        self._models = dm_models
        self.account_name = account_name
        self.from_alias = from_alias

    def send(
        self, recipient: str, subject: str, body: str
    ) -> SendResult:
        try:
            req = self._models.SingleSendMailRequest(
                account_name=self.account_name,
                from_alias=self.from_alias,
                address_type=1,
                to_address=recipient,
                subject=subject,
                html_body=body,
            )
            resp = self.client.single_send_mail(req)
            request_id = resp.body.request_id if resp and resp.body else ""
            return SendResult(success=True, vendor_receipt_id=request_id or "")
        except Exception as e:  # noqa: BLE001
            log.exception("aliyun_email_send_failed")
            err_str = str(e)
            retryable = (
                "Throttling" in err_str
                or "timeout" in err_str.lower()
                or "500" in err_str
            )
            return SendResult(success=False, error=err_str, retryable=retryable)


def build_from_settings() -> Optional[Channel]:
    """从 Settings 构建真实邮件通道；缺失配置返回 None。"""
    from app.config import get_settings

    s = get_settings()
    if not s.aliyun_access_key_id or not s.aliyun_access_key_secret:
        return None
    if not s.aliyun_dm_account_name:
        return None
    return EmailAliyunChannel(
        access_key_id=s.aliyun_access_key_id,
        access_key_secret=s.aliyun_access_key_secret,
        region=s.aliyun_region,
        account_name=s.aliyun_dm_account_name,
        from_alias=s.aliyun_dm_from_alias or s.aliyun_dm_account_name,
    )
