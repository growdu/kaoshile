"""tokens 单元测试。"""
from __future__ import annotations

import time

import pytest
from freezegun import freeze_time

from app.domain.tokens import InvalidToken, sign, verify


class TestSignAndVerify:
    """签发 + 校验 round-trip。"""

    def test_roundtrip_basic(self):
        token = sign({"sub_id": "abc", "action": "confirm"})
        payload = verify(token)
        assert payload["sub_id"] == "abc"
        assert payload["action"] == "confirm"
        assert isinstance(payload["exp"], int)

    def test_roundtrip_chinese_payload(self):
        token = sign({"sub_id": "中文-id", "action": "cancel", "note": "你好"})
        payload = verify(token)
        assert payload["sub_id"] == "中文-id"
        assert payload["note"] == "你好"

    def test_roundtrip_long_payload(self):
        token = sign({"big": "x" * 10000})
        payload = verify(token)
        assert len(payload["big"]) == 10000

    def test_payload_sort_independent(self):
        """同样 payload 不同顺序签出相同 token。"""
        t1 = sign({"a": 1, "b": 2})
        t2 = sign({"b": 2, "a": 1})
        assert t1 == t2


class TestInvalidToken:
    """错误 / 篡改 / 过期。"""

    def test_empty_raises(self):
        with pytest.raises(InvalidToken):
            verify("")

    def test_malformed_no_dot_raises(self):
        with pytest.raises(InvalidToken, match="malformed"):
            verify("nodot")

    def test_only_dot_raises(self):
        with pytest.raises(InvalidToken, match="malformed"):
            verify(".")

    def test_bad_signature_raises(self):
        token = sign({"a": 1})
        bad = token[:-2] + ("ff" if token[-2:] != "ff" else "00")
        with pytest.raises(InvalidToken, match="bad signature"):
            verify(bad)

    def test_tampered_payload_raises(self):
        token = sign({"a": 1})
        tampered = token + "abc"
        with pytest.raises(InvalidToken, match="bad signature"):
            verify(tampered)

    def test_wrong_secret(self):
        """monkeypatch _secret 函数 → verify 拒绝。"""
        import app.domain.tokens as tokens_mod

        token = sign({"a": 1})
        original = tokens_mod._secret
        tokens_mod._secret = lambda: b"different-secret-32-bytes-or-more-padding"  # noqa: SLF001
        try:
            with pytest.raises(InvalidToken):
                verify(token)
        finally:
            tokens_mod._secret = original  # noqa: SLF001

    def test_expired_raises(self):
        """签发后超过 ttl，verify 抛 expired。"""
        with freeze_time("2026-10-13 12:00:00"):
            token = sign({"a": 1}, ttl_days=1)
        with freeze_time("2026-10-15 12:00:01"):
            with pytest.raises(InvalidToken, match="expired"):
                verify(token)

    def test_just_before_expiry_passes(self):
        with freeze_time("2026-10-13 12:00:00"):
            token = sign({"a": 1}, ttl_days=1)
        with freeze_time("2026-10-14 11:59:59"):
            payload = verify(token)
            assert payload["a"] == 1


class TestTtlBehavior:
    """ttl_days 参数生效。"""

    def test_default_ttl_is_30_days(self):
        with freeze_time("2026-10-13 12:00:00"):
            token = sign({"a": 1})
            payload = verify(token)
            expected_exp = int(time.time()) + 30 * 86400
            assert payload["exp"] == expected_exp

    def test_custom_ttl(self):
        with freeze_time("2026-10-13 12:00:00"):
            token = sign({"a": 1}, ttl_days=7)
            payload = verify(token)
            expected = int(time.time()) + 7 * 86400
            assert payload["exp"] == expected

    def test_ttl_zero_is_already_expired(self):
        with freeze_time("2026-10-13 12:00:00"):
            token = sign({"a": 1}, ttl_days=0)
        with freeze_time("2026-10-13 12:00:01"):
            with pytest.raises(InvalidToken, match="expired"):
                verify(token)
