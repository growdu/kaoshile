"""模板管理 API 集成测试。"""
from __future__ import annotations

import bcrypt
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


def _admin_token(client: TestClient) -> str:
    pwd = "secret"
    h = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
    os.environ["MANAGE_PASSWORD_HASH"] = h
    r = client.post(
        "/api/manage/login", json={"username": "admin", "password": pwd}
    )
    return r.json()["data"]["token"]


class TestTemplateDefault:
    """默认模板（未覆盖时）。"""

    def test_get_default_template(self, client):
        token = _admin_token(client)
        r = client.get(
            "/api/manage/templates/EMAIL_TEMPLATE",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["channel"] == "email"
        assert body["data"]["is_default"] is True
        assert "取消订阅" in body["data"]["body"]

    def test_unknown_template_404(self, client):
        token = _admin_token(client)
        r = client.get(
            "/api/manage/templates/MADE_UP",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404


class TestUpdateAndReset:
    """更新与重置。"""

    def test_update_template(self, client):
        token = _admin_token(client)
        r = client.put(
            "/api/manage/templates/EMAIL_TEMPLATE",
            json={"body": "新的邮件文案 {exam_name}", "subject": "新主题"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["updated_by"] == "admin"
        # 之后取详情，应返回自定义内容
        r2 = client.get(
            "/api/manage/templates/EMAIL_TEMPLATE",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert "新的邮件文案" in r2.json()["data"]["body"]
        assert r2.json()["data"]["updated_by"] == "admin"

    def test_unknown_template_update_400(self, client):
        token = _admin_token(client)
        r = client.put(
            "/api/manage/templates/MADE_UP",
            json={"body": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "unknown_template"

    def test_reset_template(self, client):
        token = _admin_token(client)
        # 先覆盖
        client.put(
            "/api/manage/templates/EMAIL_TEMPLATE",
            json={"body": "new"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # 再重置
        r = client.delete(
            "/api/manage/templates/EMAIL_TEMPLATE",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        # 之后取详情应回到默认
        r2 = client.get(
            "/api/manage/templates/EMAIL_TEMPLATE",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.json()["data"]["is_default"] is True


class TestList:
    """列表。"""

    def test_empty_list(self, client):
        token = _admin_token(client)
        r = client.get(
            "/api/manage/templates",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["items"] == []

    def test_after_update_shows_in_list(self, client):
        token = _admin_token(client)
        client.put(
            "/api/manage/templates/EMAIL_TEMPLATE",
            json={"body": "覆盖"},
            headers={"Authorization": f"Bearer {token}"},
        )
        r = client.get(
            "/api/manage/templates",
            headers={"Authorization": f"Bearer {token}"},
        )
        items = r.json()["data"]["items"]
        names = [t["name"] for t in items]
        assert "EMAIL_TEMPLATE" in names


class TestAuth:
    """鉴权。"""

    def test_no_token_401(self, client):
        r = client.get("/api/manage/templates")
        assert r.status_code == 401
