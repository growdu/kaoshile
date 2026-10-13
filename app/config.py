"""配置层。

使用 pydantic-settings 从环境变量 / `.env` 读取。缺失关键凭据时 fail-fast。
详见 docs/design.md §13。
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。

    - 必填字段：缺失时 Pydantic 抛 ValidationError，启动 fail-fast。
    - 非凭据字段有默认值；凭据类（link_secret、access_key 等）必须有显式值或测试占位。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用
    app_env: str = Field(default="dev", description="dev / test / prod")
    app_port: int = Field(default=8000)
    timezone: str = Field(default="Asia/Shanghai")

    # 数据
    database_url: str = Field(default="sqlite:///./data/app.db")

    # 鉴权 / token
    link_secret: str = Field(
        ...,
        min_length=32,
        description="HMAC 签名密钥（订阅 / 退订链接）。生产用 32+ 字节随机。",
    )
    manage_username: str = Field(default="admin")
    manage_password_hash: str = Field(
        ...,
        description="bcrypt 哈希。生产中由 manage 命令生成。",
    )

    # 阿里云
    aliyun_region: str = Field(default="cn-hangzhou")
    aliyun_access_key_id: str = Field(default="")
    aliyun_access_key_secret: str = Field(default="")
    aliyun_dm_account_name: str = Field(default="")
    aliyun_dm_from_alias: str = Field(default="")
    aliyun_sms_sign_name: str = Field(default="")
    aliyun_sms_template_code: str = Field(default="")

    # 日志
    log_level: str = Field(default="INFO")

    # 通知策略
    verification_warn_days: int = Field(default=30, description="复核告警阈值（天）")
    verification_expire_days: int = Field(default=90, description="未复核自动 draft 阈值（天）")


def get_settings() -> Settings:
    """工厂函数：每次调用返回新实例。

    测试中可通过 monkeypatch.setenv 重新触发构造。
    """
    return Settings()  # type: ignore[call-arg]
