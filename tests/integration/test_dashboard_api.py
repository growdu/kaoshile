"""数据看板 API 集成测试。"""
from __future__ import annotations

import bcrypt
import os
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import create_app
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
def client() -> TestClient:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # 灌入 demo 数据
    old = datetime.utcnow() - timedelta(days=60)
    recent = datetime.utcnow() - timedelta(days=5)
    with SessionLocal() as s:
        e1 = Exam(
            id=100,
            name="热考试 A",
            category="IT",
            registration_start=datetime(2026, 8, 1),
            registration_end=datetime(2026, 8, 31),
            exam_date=datetime(2026, 11, 7),
            source_url="https://x",
            status=ExamStatus.open,
            last_verified_at=recent,
        )
        e2 = Exam(
            id=200,
            name="冷考试 B",
            category="财经",
            registration_start=datetime(2026, 6, 1),
            registration_end=datetime(2026, 6, 30),
            exam_date=datetime(2026, 9, 5),
            source_url="https://x",
            status=ExamStatus.open,
            last_verified_at=old,  # 过期未复核
        )
        s.add_all([e1, e2])
        s.commit()
        # 5 个 active sub 到 e1，1 个到 e2
        for i in range(5):
            s.add(
                Subscription(
                    id=str(uuid.uuid4()),
                    exam_id=e1.id,
                    email=f"a{i}@example.com",
                    phone="13800138000",
                    confirm_token=f"c{i}",
                    cancel_token=f"x{i}",
                    status=SubscriptionStatus.active,
                )
            )
        s.add(
            Subscription(
                id=str(uuid.uuid4()),
                exam_id=e2.id,
                email="b@example.com",
                phone="13800138001",
                confirm_token="cb",
                cancel_token="xb",
                status=SubscriptionStatus.active,
            )
        )
        # 通知 log：3 sent + 1 failed（最近 7 天）
        for i in range(3):
            s.add(
                NotificationLog(
                    id=str(uuid.uuid4()),
                    subscription_id=str(uuid.uuid4()),
                    exam_id=e1.id,
                    node_type=NodeType.exam_day,
                    channel=NotificationChannel.email,
                    status=NotificationStatus.sent,
                    attempt_count=1,
                    sent_at=datetime.utcnow() - timedelta(days=1),
                )
            )
        s.add(
            NotificationLog(
                id=str(uuid.uuid4()),
                subscription_id=str(uuid.uuid4()),
                exam_id=e1.id,
                node_type=NodeType.exam_day,
                channel=NotificationChannel.sms,
                status=NotificationStatus.failed,
                attempt_count=3,
                sent_at=datetime.utcnow() - timedelta(days=2),
            )
        )
        s.commit()

    import app.infra.db as db_mod

    db_mod._engine = engine
    db_mod._session_factory = SessionLocal

    app = create_app()
    with TestClient(app) as c:
        yield c


def _admin_token(client: TestClient) -> str:
    pwd = "secret"
    h = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
    os.environ["MANAGE_PASSWORD_HASH"] = h
    r = client.post(
        "/api/manage/login", json={"username": "admin", "password": pwd}
    )
    return r.json()["data"]["token"]


class TestOverview:
    """/api/manage/dashboard/overview。"""

    def test_returns_counts(self, client):
        token = _admin_token(client)
        r = client.get(
            "/api/manage/dashboard/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        d = body["data"]
        assert d["exams_total"] == 2
        assert d["subscriptions_total"] == 6
        assert d["subscriptions_active"] == 6
        assert "sent" in d["notifications_by_status"]
        assert d["notifications_by_status"]["sent"] == 3


class TestExamHeatmap:
    """/api/manage/dashboard/exam-heatmap。"""

    def test_orders_by_active_subs(self, client):
        token = _admin_token(client)
        r = client.get(
            "/api/manage/dashboard/exam-heatmap",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        # 热考试 A（5 sub）应排第一
        assert items[0]["name"] == "热考试 A"
        assert items[0]["active_subs"] == 5
        # 冷考试 B（1 sub）排第二
        assert items[1]["name"] == "冷考试 B"
        assert items[1]["active_subs"] == 1


class TestSuccessRate:
    """/api/manage/dashboard/notification-success-rate。"""

    def test_success_rate_calculation(self, client):
        token = _admin_token(client)
        r = client.get(
            "/api/manage/dashboard/notification-success-rate",
            params={"days": 30},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        d = r.json()["data"]
        # 3 sent / (3+1) = 0.75
        assert d["sent"] == 3
        assert d["failed"] == 1
        assert abs(d["success_rate"] - 0.75) < 0.001

    def test_no_data_full_success(self, client):
        # 删除全部 log → rate = 1.0
        with SessionFactory() as s:
            for n in s.query(NotificationLog).all():
                s.delete(n)
            s.commit()
        token = _admin_token(client)
        r = client.get(
            "/api/manage/dashboard/notification-success-rate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json()["data"]["success_rate"] == 1.0


class TestStaleExams:
    """/api/manage/dashboard/stale-exams。"""

    def test_returns_only_stale(self, client):
        token = _admin_token(client)
        r = client.get(
            "/api/manage/dashboard/stale-exams",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        # 只有冷考试 B 过期未复核
        assert len(items) == 1
        assert items[0]["name"] == "冷考试 B"


class TestAuthRequired:
    """所有 dashboard 端点都需要管理员鉴权。"""

    def test_no_token_401(self, client):
        for path in (
            "/api/manage/dashboard/overview",
            "/api/manage/dashboard/exam-heatmap",
            "/api/manage/dashboard/notification-success-rate",
            "/api/manage/dashboard/stale-exams",
        ):
            r = client.get(path)
            assert r.status_code == 401, f"{path} 应 401"


# helper for tests
from sqlalchemy.orm import sessionmaker as _sm  # noqa: E402


def SessionFactory():
    import app.infra.db as db_mod

    return db_mod._session_factory()  # type: ignore[attr-defined]
