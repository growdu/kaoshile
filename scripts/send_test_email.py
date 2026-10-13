"""联通性脚本：发送一封测试邮件到指定地址。

使用前：
1. 在 .env 中填好 ALIYUN_ACCESS_KEY_ID / SECRET / DM_ACCOUNT_NAME / FROM_ALIAS；
2. 在阿里云 DirectMail 控制台确认发件域名已配置；
3. python scripts/send_test_email.py <recipient@example.com>

注意：仅在生产环境调试时运行；CI 不调用。
"""
from __future__ import annotations

import sys

from app.config import get_settings
from app.notification.email_aliyun import EmailAliyunChannel
from app.notification.sms_aliyun import SmsAliyunChannel


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: send_test_email.py <recipient@example.com>")
        return 1
    recipient = sys.argv[1]
    s = get_settings()
    print(
        f"region={s.aliyun_region} account={s.aliyun_dm_account_name} "
        f"alias={s.aliyun_dm_from_alias}"
    )

    print("=== email ===")
    if not s.aliyun_dm_account_name:
        print("ALIYUN_DM_ACCOUNT_NAME 未配置")
        return 1
    try:
        email_ch = EmailAliyunChannel(
            access_key_id=s.aliyun_access_key_id,
            access_key_secret=s.aliyun_access_key_secret,
            region=s.aliyun_region,
            account_name=s.aliyun_dm_account_name,
            from_alias=s.aliyun_dm_from_alias or s.aliyun_dm_account_name,
        )
        result = email_ch.send(
            recipient=recipient,
            subject="【kaoshile】联通性测试",
            body="<h1>这是一封测试邮件</h1><p>如果你收到，说明阿里云 DirectMail 通道正常。</p>",
        )
        print("email result:", result)
    except Exception as e:  # noqa: BLE001
        print("email send exception:", e)

    print("=== sms ===")
    if not s.aliyun_sms_sign_name or not s.aliyun_sms_template_code:
        print("ALIYUN_SMS_SIGN_NAME / ALIYUN_SMS_TEMPLATE_CODE 未配置；跳过短信")
        return 0
    try:
        sms_ch = SmsAliyunChannel(
            access_key_id=s.aliyun_access_key_id,
            access_key_secret=s.aliyun_access_key_secret,
            sign_name=s.aliyun_sms_sign_name,
            template_code=s.aliyun_sms_template_code,
        )
        result = sms_ch.send(
            recipient=recipient,
            subject="",
            body="这是一条测试短信。如果你收到，说明阿里云 SMS 通道正常。",
        )
        print("sms result:", result)
    except Exception as e:  # noqa: BLE001
        print("sms send exception:", e)

    return 0


if __name__ == "__main__":
    sys.exit(main())
