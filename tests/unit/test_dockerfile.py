"""Dockerfile / docker-compose 静态校验。"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestDockerfile:
    """Dockerfile 关键指令。"""

    @pytest.fixture
    def dockerfile(self) -> str:
        return (REPO_ROOT / "Dockerfile").read_text()

    def test_exists(self):
        assert (REPO_ROOT / "Dockerfile").exists()

    def test_uses_python_311(self, dockerfile):
        assert re.search(r"FROM python:3\.11", dockerfile) is not None

    def test_exposes_8000(self, dockerfile):
        assert "EXPOSE 8000" in dockerfile

    def test_runs_alembic_migration(self, dockerfile):
        assert "alembic upgrade head" in dockerfile

    def test_runs_uvicorn(self, dockerfile):
        assert "uvicorn" in dockerfile

    def test_healthcheck_uses_healthz(self, dockerfile):
        assert "/healthz" in dockerfile


class TestDockerCompose:
    """docker-compose.yml。"""

    @pytest.fixture
    def compose(self) -> str:
        return (REPO_ROOT / "docker-compose.yml").read_text()

    def test_exists(self):
        assert (REPO_ROOT / "docker-compose.yml").exists()

    def test_has_api_service(self, compose):
        assert "services:" in compose
        assert "api:" in compose

    def test_maps_8000(self, compose):
        assert "8000:8000" in compose

    def test_uses_persistent_volume(self, compose):
        assert "volumes:" in compose
        assert "kaoshile-data:" in compose

    def test_healthcheck_in_compose(self, compose):
        assert "healthcheck:" in compose


class TestDockerignore:
    """.dockerignore。"""

    def test_exists(self):
        assert (REPO_ROOT / ".dockerignore").exists()

    def test_excludes_venv(self):
        text = (REPO_ROOT / ".dockerignore").read_text()
        assert ".venv" in text

    def test_excludes_env(self):
        text = (REPO_ROOT / ".dockerignore").read_text()
        assert ".env" in text
