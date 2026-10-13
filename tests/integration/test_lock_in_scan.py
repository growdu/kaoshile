"""node_scanner 与分布式锁协同的集成测试。"""
from __future__ import annotations

from datetime import datetime
import uuid

import pytest
from freezegun import freeze_time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.notification.mock import MockChannel
from app.notification.registry import register, reset_for_test
from app.repository.models import Exam, Subscription
from app.repository.orm import Base, ExamStatus, SubscriptionStatus
from app.scheduler.distributed_lock import InMemoryLock
from app.scheduler.node_scanner import scan_now


@pytest.fixture
def session_factory():
    reset_for_test()
    register(MockChannel("email"))

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
        registration_start=datetime(2026, 1, 1, tzinfo=__import__("app.infra.time", fromlist=[""]).TZ_UTC),
        registration_end=datetime(2026, 1, 31, tzinfo=__import__("app.infra.time", fromlist=[""]).TZ_UTC),
        exam_date=datetime(2026, 11, 7, 9, 0, tzinfo=__import__("app.infra.time", fromlist=[""]).TZ_UTC),
        source_url="https://x",
        status=ExamStatus.open,
    )
    with SessionLocal() as s:
        s.add(exam)
        s.commit()
        sub = Subscription(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            email="u@e.com",
            phone="13800138000",
            confirm_token="c",
            cancel_token="x",
            status=SubscriptionStatus.active,
            channels=["email"],
            reminder_level="standard",
        )
        s.add(sub)
        s.commit()
    return SessionLocal


class TestLockSkips:
    """持有锁时跳过扫描。"""

    def test_returns_zero_when_lock_held(self, session_factory):
        lock = InMemoryLock()
        # 预占锁
        lock.try_acquire("node_scanner", ttl_seconds=60)
        n = scan_now(session_factory, lock=lock)
        assert n == 0


class TestLockNormal:
    """未持锁时正常跑。"""

    def test_acquires_and_releases(self, session_factory):
        lock = InMemoryLock()
        with freeze_time("2026-11-06 09:00:30", tz_offset=0):
            n = scan_now(session_factory, lock=lock)
        assert n > 0
        # 锁已被释放，下一次可拿到
        token = lock.try_acquire("node_scanner", ttl_seconds=60)
        assert token is not None
