"""HMAC 签名 token：订阅确认 / 退订链接使用。

格式：`<base64url-payload>.<hex-sha256-signature>`

约定：
- payload 是 JSON dict，必须含 `exp`（unix 秒时间戳）；
- 默认 ttl 30 天；
- LINK_SECRET 从 settings 注入；
- 校验失败抛 InvalidToken。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.config import get_settings


class InvalidToken(Exception):
    """token 校验失败（签名错 / 篡改 / 过期 / 格式错）。"""


def _b64u_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64u_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def _secret() -> bytes:
    return get_settings().link_secret.encode()


def sign(payload: dict[str, Any], ttl_days: int = 30) -> str:
    """签发 token。

    自动加入 `exp` 字段（默认 30 天后过期）。
    返回 `<b64u-json>.<hex-sig>`。
    """
    enriched = {**payload, "exp": int(time.time()) + ttl_days * 86400}
    body = _b64u_encode(
        json.dumps(enriched, sort_keys=True, separators=(",", ":")).encode()
    )
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify(token: str) -> dict[str, Any]:
    """校验 token 并返回 payload dict。

    Raises:
        InvalidToken: 格式错 / 签名错 / 篡改 / 过期
    """
    if not isinstance(token, str) or "." not in token:
        raise InvalidToken("malformed token")
    body, _, sig = token.rpartition(".")
    if not body or not sig:
        raise InvalidToken("malformed token")
    expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise InvalidToken("bad signature")
    try:
        payload = json.loads(_b64u_decode(body))
    except (ValueError, TypeError) as e:
        raise InvalidToken(f"bad payload: {e}") from e
    if not isinstance(payload, dict):
        raise InvalidToken("payload not dict")
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise InvalidToken("missing exp")
    if exp < int(time.time()):
        raise InvalidToken("expired")
    return payload


def action(token: str) -> str:
    """便捷读取 token 的 action 字段。"""
    return verify(token)["action"]
