"""模板渲染单元测试。"""
from __future__ import annotations

from datetime import datetime

from app.notification.templates.render import (
    NODE_LABEL,
    render,
    render_confirm_email,
    render_confirm_sms,
    render_reminder_email,
    render_reminder_sms,
)


class TestRenderBasic:
    """render 函数基础行为。"""

    def test_simple_substitution(self):
        assert render("hi {name}", {"name": "alice"}) == "hi alice"

    def test_missing_key_kept(self):
        assert render("hi {name} {missing}", {"name": "alice"}) == "hi alice {missing}"

    def test_datetime_formatted(self):
        when = datetime(2026, 11, 7, 9, 0)
        out = render("at {when}", {"when": when})
        assert "2026-11-07" in out
        # Asia/Shanghai 时区缩写可能为 CST（CST=UTC+8）或 Shanghai
        assert "CST" in out or "Shanghai" in out

    def test_multiple_substitutions(self):
        out = render("{a} + {b}", {"a": "1", "b": "2"})
        assert out == "1 + 2"

    def test_no_substitutions(self):
        assert render("plain text", {}) == "plain text"


class TestNodeLabels:
    """节点标签。"""

    def test_all_five_nodes(self):
        expected = {
            "registration_start",
            "registration_end",
            "payment_end",
            "admission_start",
            "exam_day",
        }
        assert set(NODE_LABEL.keys()) == expected


class TestReminderEmail:
    """考试提醒邮件。"""

    def test_contains_exam_name_and_unsubscribe(self):
        when = datetime(2026, 11, 7, 9, 0)
        out = render_reminder_email(
            exam_name="信息系统项目管理师",
            organizer="工信部",
            node_type="exam_day",
            when=when,
            official_url="https://www.cpta.com.cn/x",
            unsubscribe_url="/s/token-here",
        )
        assert "信息系统项目管理师" in out
        assert "考试日" in out
        assert "/s/token-here" in out
        assert "https://www.cpta.com.cn/x" in out

    def test_unknown_node_falls_back_to_key(self):
        when = datetime(2026, 11, 7, 9, 0)
        out = render_reminder_email(
            exam_name="x",
            organizer="y",
            node_type="made_up",
            when=when,
            official_url="u",
            unsubscribe_url="uu",
        )
        assert "made_up" in out  # 未知节点保留 key


class TestReminderSms:
    """短信。"""

    def test_contains_key_fields(self):
        when = datetime(2026, 11, 7, 9, 0)
        out = render_reminder_sms(
            exam_name="x",
            node_type="exam_day",
            when=when,
            official_url="u",
            unsubscribe_url="uu",
        )
        assert "x" in out
        assert "考试日" in out
        assert "uu" in out

    def test_within_sms_length(self):
        """短信不应过长（v1 简单检查 < 300 字符）。"""
        when = datetime(2026, 11, 7, 9, 0)
        out = render_reminder_sms(
            exam_name="x" * 20,
            node_type="exam_day",
            when=when,
            official_url="u",
            unsubscribe_url="uu",
        )
        assert len(out) < 300


class TestConfirmTemplates:
    """订阅确认。"""

    def test_confirm_email_has_links(self):
        out = render_confirm_email(
            exam_name="x",
            confirm_url="/c/c1",
            unsubscribe_url="/s/s1",
        )
        assert "/c/c1" in out
        assert "/s/s1" in out

    def test_confirm_sms_has_link(self):
        out = render_confirm_sms(exam_name="x", confirm_url="/c/c1")
        assert "/c/c1" in out
