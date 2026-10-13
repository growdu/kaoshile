"""订阅 API 集成测试。"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import create_app
from app.notification.mock import MockChannel
from app.notification.registry import register, reset_for_test
from app.repository.models import Exam
from app.repository.orm import Base, ExamStatus


@pytest.fixture
def client() -> TestClient:
    """TestClient + MockChannel 注册 + 内存 SQLite 建表 + 灌入 1 场考试。"""
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
        name="信息系统项目管理师 2026 下",
        category="IT",
        organizer="工信部",
        registration_start=datetime(2026, 8, 15),
        registration_end=datetime(2026, 9, 5),
        payment_end=datetime(2026, 9, 10),
        exam_date=datetime(2026, 11, 7, 9, 0),
        source_url="https://www.cpta.com.cn/x",
        status=ExamStatus.open,
    )
    closed_exam = Exam(
        name="一级建造师 2026 已截止",
        category="工程",
        organizer="住建部",
        registration_start=datetime(2026, 6, 15),
        registration_end=datetime(2026, 7, 15),
        exam_date=datetime(2026, 9, 20),
        source_url="https://www.cpta.com.cn/y",
        status=ExamStatus.registration_closed,
    )
    with SessionLocal() as s:
        s.add_all([exam, closed_exam])
        s.commit()

    import app.infra.db as db_mod

    db_mod._engine = engine
    db_mod._session_factory = SessionLocal

    app = create_app()
    with TestClient(app) as c:
        yield c


def _exam_id(client: TestClient) -> int:
    """取得第一个 open 考试的 id。"""
    r = client.get("/api/exams", params={"status": "open"})
    return r.json()["data"]["items"][0]["id"]


class TestCreateSubscription:
    """POST /api/subscriptions。"""

    def test_happy(self, client):
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "u@example.com",
                "phone": "13800138000",
                "level": "standard",
                "channels": ["email", "sms"],
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        data = body["data"]
        assert data["status"] == "pending"
        assert data["confirm_url"].startswith("/c/")
        assert data["cancel_url"].startswith("/s/")
        assert "exam_day" in data["send_times"]

    def test_invalid_email_400(self, client):
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "not-email",
                "phone": "13800138000",
                "level": "standard",
            },
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_email"

    def test_phone_too_short_422(self, client):
        """phone 太短由 pydantic 边界校验拒。"""
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "u@example.com",
                "phone": "1234",
                "level": "standard",
            },
        )
        assert r.status_code == 422

    def test_phone_non_digit_400(self, client):
        """phone 长度够但不是数字 → 业务拒。"""
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "u@example.com",
                "phone": "abcdefghijk",
                "level": "standard",
            },
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_phone"

    def test_invalid_level_400(self, client):
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "u@example.com",
                "phone": "13800138000",
                "level": "foo",
            },
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_level"

    def test_invalid_channels_400(self, client):
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "u@example.com",
                "phone": "13800138000",
                "channels": ["wechat"],
            },
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_channels"

    def test_exam_not_found_400(self, client):
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": 9999,
                "email": "u@example.com",
                "phone": "13800138000",
            },
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "exam_not_found"

    def test_exam_not_open_400(self, client):
        # 找一个 registration_closed 的考试
        list_resp = client.get("/api/exams", params={"status": "registration_closed"})
        eid = list_resp.json()["data"]["items"][0]["id"]
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "u@example.com",
                "phone": "13800138000",
            },
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "exam_not_open"

    def test_email_is_lowercased(self, client):
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "U@Example.COM",
                "phone": "13800138000",
                "channels": ["email"],
            },
        )
        assert r.status_code == 200
        # 数据库中应是小写
        from sqlalchemy import select

        from app.repository.models import Subscription

        with _session_factory() as s:
            sub = s.execute(select(Subscription)).scalars().first()
            assert sub is not None
            assert sub.email == "u@example.com"


def _session_factory():
    """便利：取得测试中的 session 工厂。"""
    import app.infra.db as db_mod

    return db_mod._session_factory()  # type: ignore[misc]


class TestConfirm:
    """GET /api/subscriptions/confirm。"""

    def test_happy(self, client):
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "u@example.com",
                "phone": "13800138000",
                "channels": ["email"],
            },
        )
        token = r.json()["data"]["confirm_url"].split("/c/", 1)[1]
        r2 = client.get("/api/subscriptions/confirm", params={"token": token})
        assert r2.status_code == 200
        assert r2.json()["data"]["status"] == "active"

    def test_invalid_token_400(self, client):
        r = client.get("/api/subscriptions/confirm", params={"token": "garbage"})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_token"

    def test_idempotent_already_active(self, client):
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "u@example.com",
                "phone": "13800138000",
                "channels": ["email"],
            },
        )
        token = r.json()["data"]["confirm_url"].split("/c/", 1)[1]
        r1 = client.get("/api/subscriptions/confirm", params={"token": token})
        r2 = client.get("/api/subscriptions/confirm", params={"token": token})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.json()["data"]["status"] == "active"

    def test_confirm_after_cancel_rejected(self, client):
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "u@example.com",
                "phone": "13800138000",
                "channels": ["email"],
            },
        )
        cancel_token = r.json()["data"]["cancel_url"].split("/s/", 1)[1]
        confirm_token = r.json()["data"]["confirm_url"].split("/c/", 1)[1]
        client.post("/api/subscriptions/cancel", json={"token": cancel_token})
        r2 = client.get("/api/subscriptions/confirm", params={"token": confirm_token})
        assert r2.status_code == 400
        assert r2.json()["error"]["code"] == "already_cancelled"


class TestCancel:
    """POST /api/subscriptions/cancel。"""

    def test_happy(self, client):
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "u@example.com",
                "phone": "13800138000",
                "channels": ["email"],
            },
        )
        token = r.json()["data"]["cancel_url"].split("/s/", 1)[1]
        r2 = client.post("/api/subscriptions/cancel", json={"token": token})
        assert r2.status_code == 200
        assert r2.json()["data"]["status"] == "cancelled"

    def test_invalid_token_400(self, client):
        r = client.post("/api/subscriptions/cancel", json={"token": "garbage"})
        assert r.status_code == 400

    def test_idempotent(self, client):
        eid = _exam_id(client)
        r = client.post(
            "/api/subscriptions",
            json={
                "exam_id": eid,
                "email": "u@example.com",
                "phone": "13800138000",
                "channels": ["email"],
            },
        )
        token = r.json()["data"]["cancel_url"].split("/s/", 1)[1]
        client.post("/api/subscriptions/cancel", json={"token": token})
        r2 = client.post("/api/subscriptions/cancel", json={"token": token})
        assert r2.status_code == 200
