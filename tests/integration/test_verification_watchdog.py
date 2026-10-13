"""verification_watchdog 集成测试。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.repository.models import Exam
from app.repository.orm import Base, ExamStatus
from app.scheduler.verification_watchdog import run


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

    old_date = datetime.utcnow() - timedelta(days=100)
    fresh_date = datetime.utcnow() - timedelta(days=5)

    exams = [
        Exam(
            name="已过期",
            category="IT",
            registration_start=datetime(2026, 1, 1),
            registration_end=datetime(2026, 1, 31),
            exam_date=datetime(2026, 5, 1),
            source_url="https://x",
            status=ExamStatus.open,
            last_verified_at=old_date,
            created_at=old_date,
        ),
        Exam(
            name="新近期",
            category="IT",
            registration_start=datetime(2026, 1, 1),
            registration_end=datetime(2026, 1, 31),
            exam_date=datetime(2026, 5, 1),
            source_url="https://x",
            status=ExamStatus.open,
            last_verified_at=fresh_date,
        ),
        Exam(
            name="从未复核但刚创建",
            category="IT",
            registration_start=datetime(2026, 1, 1),
            registration_end=datetime(2026, 1, 31),
            exam_date=datetime(2026, 5, 1),
            source_url="https://x",
            status=ExamStatus.open,
            created_at=fresh_date,
        ),
        Exam(
            name="已 draft 不动",
            category="IT",
            registration_start=datetime(2026, 1, 1),
            registration_end=datetime(2026, 1, 31),
            exam_date=datetime(2026, 5, 1),
            source_url="https://x",
            status=ExamStatus.draft,
            last_verified_at=old_date,
            created_at=old_date,
        ),
    ]
    with SessionLocal() as s:
        s.add_all(exams)
        s.commit()
    return SessionLocal


class TestWatchdog:
    """run 行为。"""

    def test_drafts_only_expired_open(self, session_factory):
        n = run(session_factory)
        assert n == 1
        with session_factory() as s:
            statuses = {e.name: e.status for e in s.query(Exam).all()}
            assert statuses["已过期"] == ExamStatus.draft
            assert statuses["新近期"] == ExamStatus.open
            assert statuses["从未复核但刚创建"] == ExamStatus.open
            assert statuses["已 draft 不动"] == ExamStatus.draft

    def test_no_change_when_all_fresh(self, session_factory):
        # 全部置为 fresh 后跑
        with session_factory() as s:
            for e in s.query(Exam).all():
                e.last_verified_at = datetime.utcnow() - timedelta(days=1)
                e.created_at = datetime.utcnow() - timedelta(days=1)
            s.commit()
        n = run(session_factory)
        assert n == 0
