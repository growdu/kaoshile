"""ORM 基础与枚举单元测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.infra.db import reset_engine_for_test
from app.repository.orm import (
    Base,
    ExamStatus,
    NodeType,
    NotificationChannel,
    NotificationStatus,
    SubscriptionStatus,
)


@pytest.fixture
def in_memory_engine() -> Engine:
    reset_engine_for_test("sqlite:///:memory:")
    return reset_engine_for_test("sqlite:///:memory:")


class TestBase:
    """Base 存在且可被继承。"""

    def test_base_is_declarative_base(self):
        assert hasattr(Base, "metadata")
        assert hasattr(Base, "registry")


class TestEnums:
    """枚举值与类型。"""

    def test_exam_status_values(self):
        assert ExamStatus.draft.value == "draft"
        assert ExamStatus.open.value == "open"
        assert ExamStatus.registration_closed.value == "registration_closed"
        assert ExamStatus.archived.value == "archived"

    def test_subscription_status_values(self):
        assert SubscriptionStatus.pending.value == "pending"
        assert SubscriptionStatus.active.value == "active"
        assert SubscriptionStatus.cancelled.value == "cancelled"

    def test_node_type_values(self):
        assert NodeType.registration_start.value == "registration_start"
        assert NodeType.registration_end.value == "registration_end"
        assert NodeType.payment_end.value == "payment_end"
        assert NodeType.admission_start.value == "admission_start"
        assert NodeType.exam_day.value == "exam_day"

    def test_notification_status_values(self):
        assert NotificationStatus.queued.value == "queued"
        assert NotificationStatus.sent.value == "sent"
        assert NotificationStatus.failed.value == "failed"

    def test_notification_channel_values(self):
        assert NotificationChannel.email.value == "email"
        assert NotificationChannel.sms.value == "sms"

    def test_enums_are_str_subclass(self):
        # str-mixin：可与字符串比较与序列化
        assert ExamStatus.open == "open"
        assert NodeType.exam_day == "exam_day"
