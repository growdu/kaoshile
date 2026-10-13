"""PII 清理集成测试。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.repository.models import Exam, Subscription
from app.repository.orm import Base, ExamStatus, SubscriptionStatus
from app.scheduler.pii_cleanup import run


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    exam = Exam(
        name="test",
        category="IT",
        registration_start=datetime(2026, 1, 1),
        registration_end=datetime(2026, 1, 31),
        exam_date=datetime(2026, 5, 1),
        source_url="https://x",
        status=ExamStatus.open,
    )
    with SessionLocal() as s:
        s.add(exam)
        s.commit()
        old_cancel = datetime.utcnow() - timedelta(days=10)
        recent_cancel = datetime.utcnow() - timedelta(days=2)
        subs = [
            Subscription(
                id=str(uuid.uuid4()),
                exam_id=exam.id,
                email="old@example.com",
                phone="13800138000",
                confirm_token="c1",
                cancel_token="x1",
                status=SubscriptionStatus.cancelled,
                cancelled_at=old_cancel,
            ),
            Subscription(
                id=str(uuid.uuid4()),
                exam_id=exam.id,
                email="recent@example.com",
                phone="13800138001",
                confirm_token="c2",
                cancel_token="x2",
                status=SubscriptionStatus.cancelled,
                cancelled_at=recent_cancel,
            ),
            Subscription(
                id=str(uuid.uuid4()),
                exam_id=exam.id,
                email="active@example.com",
                phone="13800138002",
                confirm_token="c3",
                cancel_token="x3",
                status=SubscriptionStatus.active,
                cancelled_at=old_cancel,
            ),
        ]
        s.add_all(subs)
        s.commit()
    return SessionLocal


class TestPiiCleanup:
    """run 行为。"""

    def test_cleans_old_cancelled_only(self, session_factory):
        n = run(session_factory)
        assert n == 1
        with session_factory() as s:
            for sub in s.query(Subscription).all():
                if sub.email == "recent@example.com":
                    # 7 天内退订 → 不动
                    assert sub.email == "recent@example.com"
                    assert sub.confirm_token == "c2"
                elif sub.status == SubscriptionStatus.active:
                    # active → 不动
                    assert sub.email == "active@example.com"
                    assert sub.confirm_token == "c3"
                else:
                    # 已清理
                    assert sub.email == ""
                    assert sub.phone == ""
                    assert sub.confirm_token == ""
                    assert sub.cancel_token == ""

    def test_no_change_when_all_recent(self, session_factory):
        # 把所有 cancelled_at 改为 1 天前
        with session_factory() as s:
            for sub in s.query(Subscription).all():
                if sub.status == SubscriptionStatus.cancelled:
                    sub.cancelled_at = datetime.utcnow() - timedelta(days=1)
            s.commit()
        n = run(session_factory)
        assert n == 0
