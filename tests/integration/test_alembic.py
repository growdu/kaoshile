"""alembic 迁移集成测试：升级 / 降级 / 重做。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"


def _run_alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    """调用 alembic 子命令；带测试用环境变量。"""
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["LINK_SECRET"] = "ci-test-secret-must-be-32-bytes-or-more"
    env["MANAGE_PASSWORD_HASH"] = "$2b$12$dummyhashplaceholderfortests..."
    # 强制使用项目 venv 的 alembic（uv run 即可，但这里直接用 python -m alembic 更稳）
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """每个测试一个临时 SQLite 文件路径。"""
    return tmp_path / "alembic_test.db"


def _table_names(db_path: Path) -> set[str]:
    """读取实际表名集合。"""
    if not db_path.exists():
        return set()
    eng = create_engine(f"sqlite:///{db_path}")
    try:
        return set(inspect(eng).get_table_names())
    finally:
        eng.dispose()


class TestUpgrade:
    """升级。"""

    def test_upgrade_head_creates_all_tables(self, db_path: Path):
        _run_alembic(["upgrade", "head"], db_path)
        names = _table_names(db_path)
        assert {"exam", "subscription", "notification_log"}.issubset(names)
        # alembic 自身的版本表
        assert "alembic_version" in names

    def test_upgrade_head_creates_indexes(self, db_path: Path):
        _run_alembic(["upgrade", "head"], db_path)
        eng = create_engine(f"sqlite:///{db_path}")
        try:
            insp = inspect(eng)
            for tbl in ("exam", "subscription", "notification_log"):
                idx_names = {ix["name"] for ix in insp.get_indexes(tbl)}
                assert len(idx_names) > 0, f"{tbl} 应有至少 1 个索引"
        finally:
            eng.dispose()


class TestDowngrade:
    """降级。"""

    def test_downgrade_base_drops_all_tables(self, db_path: Path):
        _run_alembic(["upgrade", "head"], db_path)
        assert "exam" in _table_names(db_path)
        _run_alembic(["downgrade", "base"], db_path)
        names = _table_names(db_path)
        assert "exam" not in names
        assert "subscription" not in names
        assert "notification_log" not in names


class TestUpgradeDowngradeRoundtrip:
    """反复升级 / 降级不应破坏。"""

    def test_repeatable(self, db_path: Path):
        for i in range(2):
            _run_alembic(["upgrade", "head"], db_path)
            assert "exam" in _table_names(db_path)
            _run_alembic(["downgrade", "base"], db_path)
            assert "exam" not in _table_names(db_path)


class TestCurrent:
    """alembic current 命令。"""

    def test_current_after_upgrade(self, db_path: Path):
        _run_alembic(["upgrade", "head"], db_path)
        result = _run_alembic(["current"], db_path)
        assert "(head)" in result.stdout
