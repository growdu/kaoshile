"""管理员鉴权：bcrypt 密码验证 + HMAC token 签发。

约定：
- manage_username / manage_password_hash 从 Settings 读取；
- 登录成功签发 HMAC token（含 role=admin，过期 1 小时）；
- token 校验失败抛 AdminAuthError；
- 失败连续 N 次锁定（v1 简化：仅记录）。
"""
from __future__ import annotations

import bcrypt
from typing import Any

from app.config import get_settings
from app.domain.tokens import InvalidToken, sign, verify


class AdminAuthError(Exception):
    """管理员鉴权失败。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AdminAuthService:
    """管理员登录 / token 签发 / 校验。"""

    TOKEN_TTL_DAYS = 1  # token 1 天有效期

    def authenticate(self, username: str, password: str) -> str:
        """用户名密码正确时签发 admin token。"""
        settings = get_settings()
        if username != settings.manage_username:
            raise AdminAuthError("bad_credentials", "用户名或密码错误")
        if not self._verify_password(password, settings.manage_password_hash):
            raise AdminAuthError("bad_credentials", "用户名或密码错误")
        return sign(
            {"role": "admin", "username": username},
            ttl_days=self.TOKEN_TTL_DAYS,
        )

    def require_admin(self, token: str) -> dict[str, Any]:
        """校验 token 是 admin。"""
        try:
            payload = verify(token)
        except InvalidToken as e:
            raise AdminAuthError("invalid_token", str(e)) from e
        if payload.get("role") != "admin":
            raise AdminAuthError("not_admin", "非管理员 token")
        return payload

    @staticmethod
    def _verify_password(plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        except (ValueError, TypeError):
            return False
