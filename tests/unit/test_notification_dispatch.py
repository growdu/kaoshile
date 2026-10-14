"""NotificationService.dispatch 单元测试（覆盖重试 / 幂等 / 写 log）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.notification.base import SendResult
from app.notification.mock import MockChannel
from app.notification.registry import register, reset_for_test
from app.repository.models import Exam, Subscription
from app.repository.notification_log_repo import NotificationLogRepository
from app.repository.orm import (
    Base,
    ExamStatus,
    NodeType,
    NotificationChannel,
    NotificationStatus,
    SubscriptionStatus,
)
from app.usecase.notification import NotificationService


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def mock_channels():
    reset_for_test()
    email = MockChannel("email")
    sms = MockChannel("sms")
    register(email)
    register(sms)
    return email, sms


def _make_sub(session: Session) -> Subscription:
    exam = Exam(
        name="信息系统项目管理师 2026",
        category="IT",
        registration_start=datetime(2026, 8, 15),
        registration_end=datetime(2026, 9, 5),
        exam_date=datetime(2026, 11, 7, 9, 0),
        source_url="https://x",
        status=ExamStatus.open,
    )
    session.add(exam)
    session.commit()
    sub = Subscription(
        id=str(uuid.uuid4()),
        exam_id=exam.id,
        email="u@example.com",
        phone="13800138000",
        confirm_token="c",
        cancel_token="x",
        status=SubscriptionStatus.active,
        channels=["email", "sms"],
    )
    session.add(sub)
    session.commit()
    return sub


class TestDispatchHappy:
    """默认 Mock 通道总成功。"""

    def test_dispatches_to_all_channels(self, session: Session, mock_channels):
        email_ch, sms_ch = mock_channels
        sub = _make_sub(session)
        svc = NotificationService(log_repo=NotificationLogRepository(session))
        ok = svc.dispatch(
            sub,
            node_type=NodeType.exam_day,
            exam_id=sub.exam_id,
            subject="hi",
            body="body",
        )
        assert ok is True
        assert email_ch.call_count == 1
        assert sms_ch.call_count == 1
        # NotificationLog 应有 2 条 sent
        from app.repository.models import NotificationLog

        logs = session.query(NotificationLog).all()
        assert len(logs) == 2
        assert all(l.status == NotificationStatus.sent for l in logs)


class TestDispatchIdempotent:
    """同一 (sub, node, channel) 重复调用不重发。"""

    def test_second_dispatch_skips(self, session: Session, mock_channels):
        email_ch, _ = mock_channels
        sub = _make_sub(session)
        svc = NotificationService(log_repo=NotificationLogRepository(session))
        svc.dispatch(
            sub,
            node_type=NodeType.exam_day,
            exam_id=sub.exam_id,
            subject="hi",
            body="body",
        )
        # 第二次
        svc.dispatch(
            sub,
            node_type=NodeType.exam_day,
            exam_id=sub.exam_id,
            subject="hi",
            body="body",
        )
        assert email_ch.call_count == 1


class TestDispatchRetry:
    """失败重试。"""

    def test_succeeds_after_two_failures(self, session: Session, mock_channels):
        email_ch, _ = mock_channels
        email_ch._fail_times = 2  # 前 2 次失败，第 3 次成功
        sub = _make_sub(session)
        svc = NotificationService(log_repo=NotificationLogRepository(session))
        with patch("app.usecase.notification.time.sleep"):  # 不真睡
            ok = svc.dispatch(
                sub,
                node_type=NodeType.exam_day,
                exam_id=sub.exam_id,
                subject="hi",
                body="body",
                max_attempts=3,
            )
        assert ok is True
        assert email_ch.call_count == 3

    def test_marks_failed_after_exhausted(self, session: Session, mock_channels):
        email_ch, _ = mock_channels
        email_ch._fail_times = 100
        sub = _make_sub(session)
        svc = NotificationService(log_repo=NotificationLogRepository(session))
        with patch("app.usecase.notification.time.sleep"):
            ok = svc.dispatch(
                sub,
                node_type=NodeType.exam_day,
                exam_id=sub.exam_id,
                subject="hi",
                body="body",
                max_attempts=3,
            )
        assert ok is False
        assert email_ch.call_count == 3
        from app.repository.models import NotificationLog

        logs = session.query(NotificationLog).all()
        assert any(l.status == NotificationStatus.failed for l in logs)


class TestDispatchNonRetryable:
    """不可重试错误立即失败。"""

    def test_non_retryable_stops_immediately(self, session: Session):
        from app.notification.base import SendResult
        from app.notification.registry import register, reset_for_test
        from app.notification.mock import MockChannel

        reset_for_test()
        ch = MockChannel("email", fail_times=100, retryable=False)
        register(ch)
        sub = _make_sub(session)
        sub.channels = ["email"]
        svc = NotificationService(log_repo=NotificationLogRepository(session))
        with patch("app.usecase.notification.time.sleep"):
            ok = svc.dispatch(
                sub,
                node_type=NodeType.exam_day,
                exam_id=sub.exam_id,
                subject="hi",
                body="body",
                max_attempts=3,
            )
        assert ok is False
        assert ch.call_count == 1  # 一次就放弃


class TestDispatchNoRetryable:
    """SendResult.retryable=False 直接结束。"""

    def test_no_retry_short_circuit(self, session: Session, mock_channels):
        email_ch, _ = mock_channels
        # 通过 mock SendResult.retryable=False
        original_send = email_ch.send

        def custom_send(*a, **kw):
            r = original_send(*a, **kw)
            r.retryable = False
            return r

        email_ch.send = custom_send  # type: ignore[assignment]
        email_ch._fail_times = 100

        sub = _make_sub(session)
        svc = NotificationService(log_repo=NotificationLogRepository(session))
        with patch("app.usecase.notification.time.sleep"):
            ok = svc.dispatch(
                sub,
                node_type=NodeType.exam_day,
                exam_id=sub.exam_id,
                subject="hi",
                body="body",
                max_attempts=3,
            )
        assert ok is False
        assert email_ch.call_count == 1
