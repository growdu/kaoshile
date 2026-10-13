"""seed_demo 集成测试：subprocess 运行脚本，写入测试 DB，校验结果。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "seed_demo.py"


def _run_seed(db_path: Path) -> None:
    """subprocess 调用 seed_demo.py，使用临时 SQLite。"""
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["LINK_SECRET"] = "ci-test-secret-must-be-32-bytes-or-more"
    env["MANAGE_PASSWORD_HASH"] = "$2b$12$dummyhashplaceholderfortests...."
    env["APP_ENV"] = "test"
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"seed failed: {result.stderr}\n{result.stdout}"


def _count_exams(db_path: Path) -> int:
    """无需 ORM，只用 sqlite3 计数。"""
    import sqlite3

    con = sqlite3.connect(db_path)
    try:
        cur = con.execute("SELECT COUNT(*) FROM exam")
        return cur.fetchone()[0]
    finally:
        con.close()


def _count_subs(db_path: Path) -> int:
    import sqlite3

    con = sqlite3.connect(db_path)
    try:
        cur = con.execute("SELECT COUNT(*) FROM subscription")
        return cur.fetchone()[0]
    finally:
        con.close()


@pytest.fixture
def fresh_db(tmp_path: Path) -> Path:
    db = tmp_path / "seed_test.db"
    # 先跑 alembic upgrade 让表存在
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db}"
    env["LINK_SECRET"] = "ci-test-secret-must-be-32-bytes-or-more"
    env["MANAGE_PASSWORD_HASH"] = "$2b$12$dummyhashplaceholderfortests...."
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return db


class TestSeedDemo:
    """scripts/seed_demo.py 行为。"""

    def test_seeds_at_least_30_exams(self, fresh_db: Path):
        _run_seed(fresh_db)
        n = _count_exams(fresh_db)
        assert n >= 30

    def test_seeds_at_least_5_subscriptions(self, fresh_db: Path):
        _run_seed(fresh_db)
        n = _count_subs(fresh_db)
        assert n >= 5

    def test_idempotent_skip_when_seeded(self, fresh_db: Path):
        _run_seed(fresh_db)
        first = _count_exams(fresh_db)
        # 再跑一次
        _run_seed(fresh_db)
        second = _count_exams(fresh_db)
        assert first == second, "重复灌入应跳过"
