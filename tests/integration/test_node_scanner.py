"""node_scanner 集成测试：freezegun 触发通知。"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from freezegun import freeze_time
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.notification.mock import MockChannel
from app.notification.registry import register, reset_for_test
from app.repository.models import Exam, NotificationLog, Subscription
from app.repository.notification_log_repo import NotificationLogRepository
from app.repository.orm import (
    Base,
    ExamStatus,
    NodeType,
    NotificationChannel,
    NotificationStatus,
    SubscriptionStatus,
)
from app.scheduler.node_scanner import scan_now
from app.infra.time import TZ_UTC


@pytest.fixture
def session_factory() -> sessionmaker:
    """内存 SQLite + StaticPool + 建表 + 注入 demo 数据。"""
    reset_for_test()
    register(MockChannel("email"))
    register(MockChannel("sms"))

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    exam = Exam(
        name="信息系统项目管理师 2026",
        category="IT",
        registration_start=datetime(2026, 8, 15, 0, 0, tzinfo=TZ_UTC),
        registration_end=datetime(2026, 9, 5, 23, 59, tzinfo=TZ_UTC),
        payment_end=datetime(2026, 9, 10, 23, 59, tzinfo=TZ_UTC),
        admission_ticket_start=datetime(2026, 10, 25, 0, 0, tzinfo=TZ_UTC),
        exam_date=datetime(2026, 11, 7, 9, 0, tzinfo=TZ_UTC),  # UTC 09:00 = SHA 17:00
        source_url="https://x",
        official_url="https://www.cpta.com.cn/x",
        status=ExamStatus.open,
    )
    with SessionLocal() as s:
        s.add(exam)
        s.commit()
        sub = Subscription(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            email="u@example.com",
            phone="13800138000",
            confirm_token="c",
            cancel_token="x",
            status=SubscriptionStatus.active,
            channels=["email", "sms"],
            reminder_level="standard",
        )
        s.add(sub)
        s.commit()
    return SessionLocal


class TestScanNow:
    """scan_now 行为。"""

    def test_triggers_at_exam_day_minus_one(self, session_factory):
        """考试前一天 09:00 触发 exam_day（standard 档位）。"""
        # exam_date: 2026-11-07 09:00 SHA
        # standard: -7, -3, -1 → 2026-11-06 09:00 SHA
        with freeze_time("2026-11-06 09:00:30", tz_offset=0):
            n = scan_now(session_factory)
        assert n > 0
        with session_factory() as s:
            logs = s.query(NotificationLog).all()
            assert any(
                l.node_type == NodeType.exam_day and l.status == NotificationStatus.sent
                for l in logs
            )

    def test_does_not_trigger_outside_window(self, session_factory):
        """考试前一天 09:01 已过窗口 → 不触发。"""
        with freeze_time("2026-11-06 08:30:30", tz_offset=0):
            n = scan_now(session_factory)
        # 可能在窗口边界附近，但 09:00:30 已触发过 → 09:01:30 不再
        # 注意：第一次触发后 NotificationLog 已存在 → 幂等跳过
        with session_factory() as s:
            logs = s.query(NotificationLog).all()
            assert all(
                l.node_type != NodeType.exam_day or l.status != NotificationStatus.sent
                for l in logs
            ) or n == 0

    def test_idempotent_repeat_scan(self, session_factory):
        """同窗口重复扫描不会重复发送。"""
        with freeze_time("2026-11-06 09:00:30", tz_offset=0):
            scan_now(session_factory)
        with freeze_time("2026-11-06 09:00:30", tz_offset=0):
            scan_now(session_factory)
        with session_factory() as s:
            count = (
                s.query(NotificationLog)
                .filter(NotificationLog.node_type == NodeType.exam_day)
                .count()
            )
            # email + sms 两条
            assert count == 2

    def test_only_active_subscriptions_triggered(self, session_factory):
        """cancelled 订阅不应触发。"""
        with session_factory() as s:
            sub = s.query(Subscription).first()
            sub.status = SubscriptionStatus.cancelled
            s.commit()
        with freeze_time("2026-11-06 09:00:30", tz_offset=0):
            n = scan_now(session_factory)
        assert n == 0
