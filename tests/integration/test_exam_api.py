"""考试目录 API 集成测试。"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from app.repository.models import Exam
from app.repository.orm import Base, ExamStatus


@pytest.fixture
def client() -> TestClient:
    """TestClient：建表 + 灌入 demo 数据。"""
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # 共享同一 in-memory 连接
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    exams = [
        Exam(
            name="信息系统项目管理师 2026 下",
            category="IT",
            organizer="工信部",
            registration_start=datetime(2026, 8, 15),
            registration_end=datetime(2026, 9, 5),
            payment_end=datetime(2026, 9, 10),
            exam_date=datetime(2026, 11, 7, 9, 0),
            source_url="https://www.cpta.com.cn/1",
            status=ExamStatus.open,
        ),
        Exam(
            name="中级会计 2026",
            category="财经",
            organizer="财政部",
            registration_start=datetime(2026, 6, 1),
            registration_end=datetime(2026, 7, 1),
            exam_date=datetime(2026, 9, 5),
            source_url="http://kzp.mof.gov.cn/2",
            status=ExamStatus.open,
        ),
        Exam(
            name="一级建造师 2026",
            category="工程",
            organizer="住建部",
            registration_start=datetime(2026, 6, 15),
            registration_end=datetime(2026, 7, 15),
            exam_date=datetime(2026, 9, 20),
            source_url="https://www.cpta.com.cn/3",
            status=ExamStatus.registration_closed,
        ),
    ]
    with SessionLocal() as s:
        s.add_all(exams)
        s.commit()

    # 覆盖全局 engine 与 session_factory
    import app.infra.db as db_mod

    db_mod._engine = engine
    db_mod._session_factory = SessionLocal

    app = create_app()
    with TestClient(app) as c:
        yield c


class TestListExams:
    """/api/exams 列表。"""

    def test_returns_ok_envelope(self, client):
        r = client.get("/api/exams")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "data" in body
        assert body["data"]["total"] >= 3

    def test_filter_by_category(self, client):
        r = client.get("/api/exams", params={"category": "IT"})
        body = r.json()
        assert body["ok"] is True
        assert all(item["category"] == "IT" for item in body["data"]["items"])

    def test_filter_by_status(self, client):
        r = client.get("/api/exams", params={"status": "registration_closed"})
        body = r.json()
        assert body["ok"] is True
        assert all(item["status"] == "registration_closed" for item in body["data"]["items"])

    def test_filter_by_query(self, client):
        r = client.get("/api/exams", params={"q": "会计"})
        body = r.json()
        assert body["ok"] is True
        assert any("会计" in item["name"] for item in body["data"]["items"])

    def test_pagination_limit_offset(self, client):
        r1 = client.get("/api/exams", params={"limit": 2, "offset": 0})
        r2 = client.get("/api/exams", params={"limit": 2, "offset": 2})
        assert len(r1.json()["data"]["items"]) <= 2
        assert len(r2.json()["data"]["items"]) <= 2

    def test_invalid_limit_rejected(self, client):
        r = client.get("/api/exams", params={"limit": 0})
        assert r.status_code == 422

    def test_invalid_status_rejected(self, client):
        r = client.get("/api/exams", params={"status": "bogus"})
        assert r.status_code == 422


class TestGetExam:
    """/api/exams/{id} 详情。"""

    def test_returns_exam(self, client):
        list_resp = client.get("/api/exams", params={"status": "open"})
        items = list_resp.json()["data"]["items"]
        assert items
        eid = items[0]["id"]
        r = client.get(f"/api/exams/{eid}")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["data"]["id"] == eid
        assert body["data"]["name"]

    def test_not_found_returns_404_envelope(self, client):
        r = client.get("/api/exams/9999")
        assert r.status_code == 404
        assert r.json()["ok"] is False
        assert r.json()["error"]["code"] == "exam_not_found"
