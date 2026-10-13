"""ORM 模型集成测试：建表 / 字段 / 唯一约束 / 索引 / 关系。"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.repository.models import Exam, NotificationLog, Subscription
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
    """内存 SQLite + 建表 + session。"""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _make_exam(**overrides) -> Exam:
    defaults = dict(
        name="信息系统项目管理师 2026 下",
        category="IT",
        organizer="工信部 / 人社部",
        registration_start=datetime(2026, 8, 15),
        registration_end=datetime(2026, 9, 5),
        payment_end=datetime(2026, 9, 10),
        admission_ticket_start=datetime(2026, 10, 25),
        exam_date=datetime(2026, 11, 7, 9, 0),
        official_url="https://example.com/official",
        source_url="https://example.com/source",
        status=ExamStatus.open,
    )
    defaults.update(overrides)
    return Exam(**defaults)


def _make_subscription(exam_id: int, **overrides) -> Subscription:
    defaults = dict(
        id=str(uuid.uuid4()),
        exam_id=exam_id,
        email="u@example.com",
        phone="13800138000",
        reminder_level="standard",
        channels=["email", "sms"],
        status=SubscriptionStatus.pending,
        confirm_token="tok-confirm",
        cancel_token="tok-cancel",
    )
    defaults.update(overrides)
    return Subscription(**defaults)


def _make_log(subscription_id: str, exam_id: int, **overrides) -> NotificationLog:
    defaults = dict(
        id=str(uuid.uuid4()),
        subscription_id=subscription_id,
        exam_id=exam_id,
        node_type=NodeType.exam_day,
        channel=NotificationChannel.email,
        status=NotificationStatus.queued,
        attempt_count=0,
    )
    defaults.update(overrides)
    return NotificationLog(**defaults)


class TestExamModel:
    """Exam 模型。"""

    def test_insert_and_read(self, session: Session):
        exam = _make_exam()
        session.add(exam)
        session.commit()
        assert exam.id is not None
        found = session.get(Exam, exam.id)
        assert found is not None
        assert found.name == "信息系统项目管理师 2026 下"
        assert found.category == "IT"
        assert found.source_url == "https://example.com/source"

    def test_status_default_draft(self, session: Session):
        exam = Exam(
            name="x",
            category="IT",
            registration_start=datetime(2026, 1, 1),
            registration_end=datetime(2026, 1, 2),
            exam_date=datetime(2026, 2, 1),
            source_url="https://example.com/source",
        )
        session.add(exam)
        session.commit()
        assert exam.status == ExamStatus.draft

    def test_table_indexes(self, session: Session):
        engine = session.get_bind()
        index_names = {ix["name"] for ix in inspect(engine).get_indexes("exam")}
        assert "ix_exam_status_reg_end" in index_names
        assert "ix_exam_last_verified_at" in index_names
        assert "ix_exam_category" in index_names


class TestSubscriptionModel:
    """Subscription 模型。"""

    def test_insert_and_read(self, session: Session):
        exam = _make_exam()
        session.add(exam)
        session.commit()
        sub = _make_subscription(exam.id)
        session.add(sub)
        session.commit()
        assert sub.id is not None
        found = session.get(Subscription, sub.id)
        assert found is not None
        assert found.channels == ["email", "sms"]

    def test_unique_email_exam_status(self, session: Session):
        """同一 (email, exam_id, status) 不允许重复。"""
        exam = _make_exam()
        session.add(exam)
        session.commit()
        s1 = _make_subscription(exam.id, confirm_token="t1", cancel_token="c1")
        s2 = _make_subscription(exam.id, confirm_token="t2", cancel_token="c2")
        session.add_all([s1, s2])
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_unique_confirm_token(self, session: Session):
        """confirm_token 全局唯一。"""
        exam1 = _make_exam()
        exam2 = _make_exam()
        session.add_all([exam1, exam2])
        session.commit()
        s1 = _make_subscription(exam1.id, confirm_token="SAME", cancel_token="c1")
        s2 = _make_subscription(
            exam2.id, confirm_token="SAME", cancel_token="c2", email="other@example.com"
        )
        session.add_all([s1, s2])
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_active_and_cancelled_coexist(self, session: Session):
        """同一 email 同一 exam：active 与 cancelled 不互斥。"""
        exam = _make_exam()
        session.add(exam)
        session.commit()
        s_active = _make_subscription(
            exam.id,
            confirm_token="t-active",
            cancel_token="c-active",
            status=SubscriptionStatus.active,
        )
        s_cancelled = _make_subscription(
            exam.id,
            confirm_token="t-cancel",
            cancel_token="c-cancel",
            status=SubscriptionStatus.cancelled,
        )
        session.add_all([s_active, s_cancelled])
        session.commit()
        assert session.query(Subscription).count() == 2


class TestNotificationLogModel:
    """NotificationLog 模型。"""

    def test_insert_and_read(self, session: Session):
        exam = _make_exam()
        session.add(exam)
        session.commit()
        sub = _make_subscription(
            exam.id, confirm_token="tc", cancel_token="cc", status=SubscriptionStatus.active
        )
        session.add(sub)
        session.commit()
        log = _make_log(sub.id, exam.id)
        session.add(log)
        session.commit()
        assert log.id is not None
        assert log.status == NotificationStatus.queued
        assert log.attempt_count == 0

    def test_unique_sub_node_channel(self, session: Session):
        """同一 (sub, node, channel) 只允许一条（幂等）。"""
        exam = _make_exam()
        session.add(exam)
        session.commit()
        sub = _make_subscription(
            exam.id, confirm_token="tc", cancel_token="cc", status=SubscriptionStatus.active
        )
        session.add(sub)
        session.commit()
        l1 = _make_log(sub.id, exam.id)
        l2 = _make_log(sub.id, exam.id)
        session.add_all([l1, l2])
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_different_channel_allowed(self, session: Session):
        """同一 (sub, node) 不同 channel 允许。"""
        exam = _make_exam()
        session.add(exam)
        session.commit()
        sub = _make_subscription(
            exam.id, confirm_token="tc", cancel_token="cc", status=SubscriptionStatus.active
        )
        session.add(sub)
        session.commit()
        l1 = _make_log(sub.id, exam.id, channel=NotificationChannel.email)
        l2 = _make_log(sub.id, exam.id, channel=NotificationChannel.sms)
        session.add_all([l1, l2])
        session.commit()
        assert session.query(NotificationLog).count() == 2


class TestCascadeDelete:
    """删除 Exam 级联清理订阅与日志。"""

    def test_deleting_exam_cascades(self, session: Session):
        exam = _make_exam()
        session.add(exam)
        session.commit()
        sub = _make_subscription(
            exam.id, confirm_token="tc", cancel_token="cc", status=SubscriptionStatus.active
        )
        session.add(sub)
        session.commit()
        log = _make_log(sub.id, exam.id, status=NotificationStatus.sent)
        session.add(log)
        session.commit()

        session.delete(exam)
        session.commit()
        assert session.query(Subscription).count() == 0
        assert session.query(NotificationLog).count() == 0
