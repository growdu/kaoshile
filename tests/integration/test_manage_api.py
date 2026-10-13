"""管理员 API 集成测试：登录 / 考试 CRUD / 订阅查询 / 通知日志。"""
from __future__ import annotations

import bcrypt
import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.main import create_app
from app.repository.models import Exam, Subscription
from app.repository.orm import Base, ExamStatus, SubscriptionStatus


@pytest.fixture
def client_with_db():
    """TestClient：内存 SQLite 建表 + 灌入 demo。"""
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
        organizer="工信部",
        registration_start=datetime(2026, 8, 15),
        registration_end=datetime(2026, 9, 5),
        exam_date=datetime(2026, 11, 7),
        source_url="https://x",
        status=ExamStatus.open,
    )
    with SessionLocal() as s:
        s.add(exam)
        s.commit()

    import app.infra.db as db_mod

    db_mod._engine = engine
    db_mod._session_factory = SessionLocal

    app = create_app()
    with TestClient(app) as c:
        yield c


def _set_admin_password(plain: str) -> str:
    """生成 bcrypt hash 并写入测试 settings。"""
    h = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()
    os.environ["MANAGE_PASSWORD_HASH"] = h
    return h


def _admin_token(client: TestClient, *, username: str = "admin", password: str = "secret") -> str:
    """登录拿 token。"""
    r = client.post(
        "/api/manage/login",
        json={"username": username, "password": password},
    )
    return r.json()["data"]["token"]


class TestLogin:
    """/api/manage/login。"""

    def test_success(self, client_with_db):
        _set_admin_password("secret")
        r = client_with_db.post(
            "/api/manage/login",
            json={"username": "admin", "password": "secret"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "token" in body["data"]
        assert body["data"]["expires_in_days"] >= 1

    def test_bad_password_401(self, client_with_db):
        _set_admin_password("secret")
        r = client_with_db.post(
            "/api/manage/login",
            json={"username": "admin", "password": "wrong"},
        )
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "bad_credentials"

    def test_bad_username_401(self, client_with_db):
        _set_admin_password("secret")
        r = client_with_db.post(
            "/api/manage/login",
            json={"username": "other", "password": "secret"},
        )
        assert r.status_code == 401


class TestAuthRequired:
    """管理端点均需鉴权。"""

    def test_no_token_401(self, client_with_db):
        r = client_with_db.get("/api/manage/exams")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"

    def test_bad_token_401(self, client_with_db):
        r = client_with_db.get(
            "/api/manage/exams",
            headers={"Authorization": "Bearer garbage"},
        )
        assert r.status_code == 401

    def test_non_admin_token_401(self, client_with_db):
        """用普通 subscription token 调管理端点 → 401。"""
        from app.domain.tokens import sign

        token = sign({"sub_id": "x", "action": "confirm"}, ttl_days=1)
        r = client_with_db.get(
            "/api/manage/exams",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "not_admin"


class TestManageExams:
    """/api/manage/exams CRUD。"""

    def test_list_exams(self, client_with_db):
        _set_admin_password("secret")
        token = _admin_token(client_with_db)
        r = client_with_db.get(
            "/api/manage/exams",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["total"] >= 1
        assert "source_url" in body["data"]["items"][0]

    def test_create_exam(self, client_with_db):
        _set_admin_password("secret")
        token = _admin_token(client_with_db)
        r = client_with_db.post(
            "/api/manage/exams",
            json={
                "name": "一级建造师 2026",
                "category": "工程",
                "registration_start": "2026-06-15T00:00:00",
                "registration_end": "2026-07-15T23:59:59",
                "exam_date": "2026-09-20T09:00:00",
                "source_url": "https://www.cpta.com.cn/y",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["name"] == "一级建造师 2026"

    def test_verify_exam_updates_last_verified(self, client_with_db):
        _set_admin_password("secret")
        token = _admin_token(client_with_db)
        # list first to get id
        list_r = client_with_db.get(
            "/api/manage/exams",
            headers={"Authorization": f"Bearer {token}"},
        )
        eid = list_r.json()["data"]["items"][0]["id"]
        # verify
        r = client_with_db.post(
            f"/api/manage/exams/{eid}/verify",
            json={"source_hash": "abc123"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["last_verified_at"] is not None
        assert body["data"]["verifier"] == "admin"
        assert body["data"]["source_url"] == body["data"]["source_url"]

    def test_update_exam_status(self, client_with_db):
        _set_admin_password("secret")
        token = _admin_token(client_with_db)
        list_r = client_with_db.get(
            "/api/manage/exams",
            headers={"Authorization": f"Bearer {token}"},
        )
        eid = list_r.json()["data"]["items"][0]["id"]
        r = client_with_db.patch(
            f"/api/manage/exams/{eid}/status",
            json={"status": "registration_closed"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "registration_closed"


class TestAdminSubscriptions:
    """/api/manage/subscriptions。"""

    def test_list_empty(self, client_with_db):
        _set_admin_password("secret")
        token = _admin_token(client_with_db)
        r = client_with_db.get(
            "/api/manage/subscriptions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["total"] == 0

    def test_list_with_filter(self, client_with_db):
        _set_admin_password("secret")
        token = _admin_token(client_with_db)
        # 灌入一条 sub
        from sqlalchemy import select

        with __import__("app.infra.db", fromlist=[""])._session_factory() as s:  # type: ignore[attr-defined]
            list_r = client_with_db.get(
                "/api/manage/exams",
                headers={"Authorization": f"Bearer {token}"},
            )
            eid = list_r.json()["data"]["items"][0]["id"]
            from app.repository.models import Subscription as Sub

            sub = Sub(
                id="sub-id-1",
                exam_id=eid,
                email="u@example.com",
                phone="13800138000",
                confirm_token="c",
                cancel_token="x",
                status=SubscriptionStatus.active,
            )
            s.add(sub)
            s.commit()

        r = client_with_db.get(
            "/api/manage/subscriptions",
            params={"status": "active"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["total"] == 1


class TestAdminHealth:
    """/api/manage/health。"""

    def test_returns_counts(self, client_with_db):
        _set_admin_password("secret")
        token = _admin_token(client_with_db)
        r = client_with_db.get(
            "/api/manage/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "exams_total" in body["data"]
        assert "subscriptions_total" in body["data"]
        assert "notifications_by_status" in body["data"]
