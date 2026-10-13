"""log 单元测试。"""
from __future__ import annotations

import json

import pytest

from app.infra.logging import (
    REDACT_KEYS,
    _redact_processor,
    configure_logging,
    get_logger,
)


def _last_json_line(capsys) -> dict:
    """从 pytest capsys 捕获的 stdout 中解析最后一行非空 JSON。"""
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines, f"expected non-empty stdout, got {out!r}"
    return json.loads(lines[-1])


class TestRedactProcessor:
    """_redact_processor 行为。"""

    def test_redacts_top_level_sensitive(self):
        event_dict = {"access_key_id": "AKIDxxxxx", "ok": True}
        result = _redact_processor(None, "info", event_dict)
        assert result["access_key_id"] == "***REDACTED***"
        assert result["ok"] is True

    def test_redacts_nested_dict(self):
        event_dict = {"outer": {"secret_key": "shhh", "ok": 1}}
        result = _redact_processor(None, "info", event_dict)
        assert result["outer"]["secret_key"] == "***REDACTED***"
        assert result["outer"]["ok"] == 1

    def test_redacts_phone_email(self):
        event_dict = {"phone": "13800138000", "email": "x@y.com", "note": "ok"}
        result = _redact_processor(None, "info", event_dict)
        assert result["phone"] == "***REDACTED***"
        assert result["email"] == "***REDACTED***"
        assert result["note"] == "ok"

    def test_redacts_token_authorization(self):
        event_dict = {"token": "t", "authorization": "Bearer x", "ok": 1}
        result = _redact_processor(None, "info", event_dict)
        assert result["token"] == "***REDACTED***"
        assert result["authorization"] == "***REDACTED***"

    def test_case_insensitive(self):
        event_dict = {"Access_Key_ID": "x"}
        result = _redact_processor(None, "info", event_dict)
        assert result["Access_Key_ID"] == "***REDACTED***"

    def test_no_redact_for_safe_keys(self):
        event_dict = {"subscription_id": "abc", "exam_id": 12, "channel": "email"}
        result = _redact_processor(None, "info", event_dict)
        assert result == event_dict

    def test_redact_keys_constant_includes_essentials(self):
        """常覆盖关键字段。"""
        for must in ("access_key_id", "secret", "phone", "email", "password", "token"):
            assert must in REDACT_KEYS


class TestConfigureLogging:
    """configure_logging 行为。"""

    def test_idempotent(self):
        configure_logging()
        configure_logging()
        # 不抛异常即可

    def test_logger_callable(self):
        configure_logging()
        log = get_logger("test")
        assert log is not None


class TestJsonOutput:
    """输出格式：JSON 且 redact 生效。"""

    def test_output_is_json(self, capsys, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        configure_logging()
        log = get_logger("test")
        log.info("hello", subscription_id="abc")
        data = _last_json_line(capsys)
        assert data["event"] == "hello"
        assert data["subscription_id"] == "abc"
        assert data["level"] == "info"

    def test_output_redacts_sensitive_fields(self, capsys, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        configure_logging()
        log = get_logger("test")
        log.info("send_sms", phone="13800138000", email="x@y.com")
        data = _last_json_line(capsys)
        assert data["phone"] == "***REDACTED***"
        assert data["email"] == "***REDACTED***"

    def test_debug_filtered_at_info_level(self, capsys, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        configure_logging()
        log = get_logger("test")
        log.debug("noisy")
        out = capsys.readouterr().out.strip()
        assert out == "", f"debug should be filtered at INFO, got: {out!r}"

    def test_debug_passed_at_debug_level(self, capsys, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        configure_logging()
        log = get_logger("test")
        log.debug("verbose")
        data = _last_json_line(capsys)
        assert data["event"] == "verbose"
        assert data["level"] == "debug"
