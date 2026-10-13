"""日志层：structlog 结构化日志 + 敏感字段 redact。

约定：
- 所有日志输出 JSON 到 stdout，便于聚合；
- 敏感字段（access_key / secret / phone / email / password / token / authorization）值替换为 '***REDACTED***'；
- 调用方使用 `get_logger(name)` 取得 logger。
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.config import get_settings

# 敏感字段名（不区分大小写）：值被 redact 为 "***REDACTED***"
REDACT_KEYS = frozenset(
    {
        "access_key",
        "access_key_id",
        "access_key_secret",
        "secret",
        "secret_key",
        "phone",
        "phone_number",
        "mobile",
        "email",
        "password",
        "password_hash",
        "token",
        "authorization",
        "cookie",
        "set_cookie",
        "link_secret",
    }
)


def _redact_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor：递归 redact 敏感字段。"""
    for key, value in list(event_dict.items()):
        if isinstance(key, str) and key.lower() in REDACT_KEYS:
            event_dict[key] = "***REDACTED***"
        elif isinstance(value, dict):
            event_dict[key] = _redact_processor(_, _, value)
    return event_dict


def configure_logging() -> None:
    """配置全局日志。应在 FastAPI lifespan 启动时调用一次。

    可重复调用，每次重新读取 LOG_LEVEL 并重置 stdout 引用。
    """
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # 标准库 logging 桥接
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,  # 覆盖之前的 basicConfig
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_processor,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,  # 测试中需要每次拿到新 logger
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """取得 logger。"""
    return structlog.get_logger(name) if name else structlog.get_logger()
