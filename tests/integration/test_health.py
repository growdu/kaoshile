"""FastAPI 应用 + /healthz + /readyz 集成测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """TestClient：每次新构造 app + 把 db 切到内存 SQLite。"""
    from app.infra.db import reset_engine_for_test

    # 让 db 走内存 SQLite（避免触碰真实 ./data/app.db）
    reset_engine_for_test("sqlite:///:memory:")
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestHealthz:
    """/healthz 始终返回 200，不依赖 db。"""

    def test_healthz_returns_ok(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["status"] == "alive"

    def test_healthz_includes_version(self, client):
        r = client.get("/healthz")
        assert r.json()["data"]["version"] == "0.1.0"


class TestReadyz:
    """/readyz 在 db 可用时返回 200。"""

    def test_readyz_returns_ready(self, client):
        r = client.get("/readyz")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["status"] == "ready"

    def test_readyz_returns_error_when_db_down(self, monkeypatch):
        """db 不可用时返回 ok=false 且 status_code 仍 200（错误响应统一信封约定）。"""
        import app.main as main_mod

        def _broken_engine():
            raise RuntimeError("db down")

        # main.py 里 `from app.infra.db import get_engine` 已经是局部引用，
        # 所以 monkeypatch 必须指向 main_mod.get_engine。
        monkeypatch.setattr(main_mod, "get_engine", _broken_engine)
        app = create_app()
        with TestClient(app) as c:
            r = c.get("/readyz")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "db_unavailable"


class TestIndex:
    """/ 元信息端点。"""

    def test_index_includes_name_and_docs_link(self, client):
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["name"] == "kaoshile"
        assert body["data"]["docs"] == "/docs"


class TestLifespan:
    """FastAPI lifespan 启动钩子。"""

    def test_lifespan_runs_init_db(self, client):
        """lifespan 跑过 init_db 后，readyz 应能成功连 db。"""
        # client fixture 已经在 __enter__ 跑完 lifespan；调用 readyz 验证副作用
        r = client.get("/readyz")
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["status"] == "ready"


class TestOpenAPI:
    """OpenAPI schema 由 FastAPI 自动生成。"""

    def test_openapi_schema_generated(self, client):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        assert schema["info"]["title"] == "kaoshile"
        assert schema["info"]["version"] == "0.1.0"
        assert "/healthz" in schema["paths"]
        assert "/readyz" in schema["paths"]
        assert "/" in schema["paths"]
