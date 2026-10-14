"""NotificationLogRepository 单元测试。"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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


def _make_exam_and_sub(session: Session) -> tuple[Exam, Subscription]:
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
    )
    session.add(sub)
    session.commit()
    return exam, sub


class TestInsertAndFind:
    """插入与查询。"""

    def test_insert_queued(self, session: Session):
        _, sub = _make_exam_and_sub(session)
        repo = NotificationLogRepository(session)
        log = repo.insert_queued(
            subscription_id=sub.id,
            exam_id=sub.exam_id,
            node_type=NodeType.exam_day,
            channel=NotificationChannel.email,
        )
        assert log.id is not None
        assert log.status == NotificationStatus.queued
        assert log.attempt_count == 0

    def test_exists_returns_true(self, session: Session):
        _, sub = _make_exam_and_sub(session)
        repo = NotificationLogRepository(session)
        repo.insert_queued(
            subscription_id=sub.id,
            exam_id=sub.exam_id,
            node_type=NodeType.exam_day,
            channel=NotificationChannel.email,
        )
        assert (
            repo.exists(
                subscription_id=sub.id,
                node_type=NodeType.exam_day,
                channel=NotificationChannel.email,
            )
            is True
        )

    def test_exists_returns_false_when_missing(self, session: Session):
        _, sub = _make_exam_and_sub(session)
        repo = NotificationLogRepository(session)
        assert (
            repo.exists(
                subscription_id=sub.id,
                node_type=NodeType.exam_day,
                channel=NotificationChannel.email,
            )
            is False
        )

    def test_find_returns_log(self, session: Session):
        exam, sub = _make_exam_and_sub(session)
        repo = NotificationLogRepository(session)
        log = repo.insert_queued(
            subscription_id=sub.id,
            exam_id=exam.id,
            node_type=NodeType.exam_day,
            channel=NotificationChannel.sms,
        )
        found = repo.find(
            subscription_id=sub.id,
            node_type=NodeType.exam_day,
            channel=NotificationChannel.sms,
        )
        assert found is not None
        assert found.id == log.id


class TestStatusTransitions:
    """状态流转。"""

    def test_mark_sent(self, session: Session):
        _, sub = _make_exam_and_sub(session)
        repo = NotificationLogRepository(session)
        log = repo.insert_queued(
            subscription_id=sub.id,
            exam_id=sub.exam_id,
            node_type=NodeType.exam_day,
            channel=NotificationChannel.email,
        )
        repo.mark_sent(log, receipt_id="receipt-1")
        assert log.status == NotificationStatus.sent
        assert log.vendor_receipt_id == "receipt-1"
        assert log.attempt_count == 1
        assert log.sent_at is not None

    def test_mark_failed(self, session: Session):
        _, sub = _make_exam_and_sub(session)
        repo = NotificationLogRepository(session)
        log = repo.insert_queued(
            subscription_id=sub.id,
            exam_id=sub.exam_id,
            node_type=NodeType.exam_day,
            channel=NotificationChannel.email,
        )
        repo.mark_failed(log, error="timeout")
        assert log.status == NotificationStatus.failed
        assert log.error_message == "timeout"
        assert log.attempt_count == 1
