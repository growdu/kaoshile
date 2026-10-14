"""账户 API 集成测试。"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import create_app
from app.repository.orm import Base


@pytest.fixture
def client() -> TestClient:
    """TestClient：内存 SQLite 建表。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    import app.infra.db as db_mod

    db_mod._engine = engine
    db_mod._session_factory = SessionLocal

    app = create_app()
    with TestClient(app) as c:
        yield c


class TestRegister:
    def test_happy(self, client):
        r = client.post(
            "/api/account/register",
            json={"email": "u@example.com", "password": "password123"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["email"] == "u@example.com"

    def test_invalid_email_400(self, client):
        r = client.post(
            "/api/account/register",
            json={"email": "bad", "password": "password123"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_email"

    def test_short_password_400(self, client):
        r = client.post(
            "/api/account/register",
            json={"email": "u@example.com", "password": "short"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "weak_password"

    def test_email_taken(self, client):
        client.post(
            "/api/account/register",
            json={"email": "u@example.com", "password": "password123"},
        )
        r = client.post(
            "/api/account/register",
            json={"email": "u@example.com", "password": "password456"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "email_taken"


class TestLogin:
    def test_happy(self, client):
        client.post(
            "/api/account/register",
            json={"email": "u@example.com", "password": "password123"},
        )
        r = client.post(
            "/api/account/login",
            json={"email": "u@example.com", "password": "password123"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "token" in body["data"]

    def test_wrong_password_401(self, client):
        client.post(
            "/api/account/register",
            json={"email": "u@example.com", "password": "password123"},
        )
        r = client.post(
            "/api/account/login",
            json={"email": "u@example.com", "password": "wrong"},
        )
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "bad_credentials"

    def test_unknown_email_401(self, client):
        r = client.post(
            "/api/account/login",
            json={"email": "noone@example.com", "password": "x12345678"},
        )
        assert r.status_code == 401


class TestForgotReset:
    def test_forgot_returns_dev_token(self, client):
        client.post(
            "/api/account/register",
            json={"email": "u@example.com", "password": "password123"},
        )
        r = client.post(
            "/api/account/forgot-password",
            json={"email": "u@example.com"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "dev_token" in body["data"]

    def test_forgot_unknown_email_silent_ok(self, client):
        r = client.post(
            "/api/account/forgot-password",
            json={"email": "ghost@example.com"},
        )
        # 不泄露存在性
        assert r.status_code == 200
        assert r.json()["data"]["dev_token"] is None

    def test_reset_password_flow(self, client):
        client.post(
            "/api/account/register",
            json={"email": "u@example.com", "password": "password123"},
        )
        tok_resp = client.post(
            "/api/account/forgot-password",
            json={"email": "u@example.com"},
        )
        token = tok_resp.json()["data"]["dev_token"]
        r = client.post(
            "/api/account/reset-password",
            json={"token": token, "new_password": "newpassword123"},
        )
        assert r.status_code == 200
        # 用新密码登录
        r2 = client.post(
            "/api/account/login",
            json={"email": "u@example.com", "password": "newpassword123"},
        )
        assert r2.status_code == 200

    def test_reset_invalid_token(self, client):
        r = client.post(
            "/api/account/reset-password",
            json={"token": "garbage", "new_password": "newpassword123"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "invalid_token"


class TestMeSubscriptions:
    def test_no_token_401(self, client):
        r = client.get("/api/account/me/subscriptions")
        assert r.status_code == 401

    def test_with_valid_token(self, client):
        client.post(
            "/api/account/register",
            json={"email": "u@example.com", "password": "password123"},
        )
        r = client.post(
            "/api/account/login",
            json={"email": "u@example.com", "password": "password123"},
        )
        token = r.json()["data"]["token"]
        r2 = client.get(
            "/api/account/me/subscriptions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["data"]["items"] == []

    def test_non_user_token_401(self, client):
        # 用 subscription token 冒充 user token
        from app.domain.tokens import sign

        token = sign({"sub_id": "x", "action": "confirm"}, ttl_days=1)
        r = client.get(
            "/api/account/me/subscriptions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 401


class TestUpdateMe:
    """PATCH /api/account/me。"""

    def _register_login(self, client, *, email="u@example.com", password="password123"):
        client.post(
            "/api/account/register",
            json={"email": email, "password": password},
        )
        r = client.post(
            "/api/account/login", json={"email": email, "password": password}
        )
        return r.json()["data"]["token"]

    def test_update_phone(self, client):
        token = self._register_login(client)
        r = client.patch(
            "/api/account/me",
            json={"phone": "13800138001"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["phone"] == "13800138001"

    def test_update_password_happy(self, client):
        token = self._register_login(client)
        r = client.patch(
            "/api/account/me",
            json={"current_password": "password123", "new_password": "newpassword456"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        # 旧密码不能再登录
        r2 = client.post(
            "/api/account/login",
            json={"email": "u@example.com", "password": "password123"},
        )
        assert r2.status_code == 401
        # 新密码可以
        r3 = client.post(
            "/api/account/login",
            json={"email": "u@example.com", "password": "newpassword456"},
        )
        assert r3.status_code == 200

    def test_update_password_wrong_current(self, client):
        token = self._register_login(client)
        r = client.patch(
            "/api/account/me",
            json={"current_password": "wrong", "new_password": "newpassword456"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "bad_credentials"

    def test_update_password_missing_current(self, client):
        token = self._register_login(client)
        r = client.patch(
            "/api/account/me",
            json={"new_password": "newpassword456"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "missing_current_password"

    def test_no_token_401(self, client):
        r = client.patch(
            "/api/account/me", json={"phone": "13800138001"}
        )
        assert r.status_code == 401
