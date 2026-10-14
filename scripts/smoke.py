"""端到端冒烟脚本：跑通主链路并打印每步结果。

执行：
    uv run python scripts/smoke.py [--fail-fast]

退出码：
    0  全部通过；
    1  存在失败步骤。

覆盖主链路：
    1. health           GET /healthz + /readyz
    2. list_exams       GET /api/exams (含 1 条明细)
    3. register_login   POST /api/account/register + login
    4. subscribe_confirm POST /api/subscriptions + GET confirm
    5. trigger_node     推进时间 + scan_now() + 检查 NotificationLog
    6. cancel           POST /api/subscriptions/cancel
    7. change_email     POST /api/account/change-email + verify
    8. dashboard        管理员登录 + GET overview

实现策略：
    - 进程内 TestClient，不依赖外部 HTTP；
    - 内存 SQLite + MockChannel，不污染生产数据；
    - 每个步骤独立为函数返回 Step，便于单元测试复用。
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, List

# 确保项目根目录可导入
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 测试运行所需的最小环境（SECRET 占位 + bcrypt mock 链路等）
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("HMAC_SECRET", "smoke-secret")
os.environ.setdefault("LINK_SECRET", "smoke-link-secret-32-bytes-min-padding!")

# admin bcrypt 占位（启动时再覆盖为真实 hash，避免 Settings 校验失败）
os.environ.setdefault("MANAGE_PASSWORD_HASH", "$2b$12$placeholderhash")


@dataclass
class Step:
    """单步结果。"""

    name: str
    ok: bool
    detail: str = ""

    def render(self) -> str:
        mark = "✅" if self.ok else "❌"
        return f"{mark} {self.name:<22} {self.detail}"


# ---------- 工具：构建内存应用 ----------


def _make_app_and_session_factory():
    """构建 in-memory 应用并返回 (TestClient, session_factory, engine)。"""
    import bcrypt
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.infra import db as db_mod
    from app.main import create_app
    from app.notification.mock import MockChannel
    from app.notification.registry import register, reset_for_test
    from app.repository.orm import Base, ExamStatus
    from app.repository.models import Exam

    # 1. 引擎 + 建表
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )

    # 2. 注入到 db 模块（API Depends get_db 读这里）
    db_mod._engine = engine
    db_mod._session_factory = SessionLocal

    # 2.5 设置 admin bcrypt 哈希（覆盖占位）
    os.environ["MANAGE_PASSWORD_HASH"] = bcrypt.hashpw(
        b"adminpass123", bcrypt.gensalt()
    ).decode()

    # 3. 注册 MockChannel
    reset_for_test()
    register(MockChannel())

    # 4. 灌入 1 条考试（明天开始报名）
    tomorrow = datetime.now() + timedelta(days=1)
    with SessionLocal() as s:  # type: ignore[call-arg]
        s.add(
            Exam(
                name="冒烟测试 / 软考",
                category="IT",
                organizer="工业和信息化部 / 人社部",
                registration_start=tomorrow,
                registration_end=tomorrow + timedelta(days=14),
                payment_end=tomorrow + timedelta(days=18),
                exam_date=tomorrow + timedelta(days=60),
                source_url="https://www.cpta.com.cn/smoke",
                official_url="https://www.cpta.com.cn/",
                status=ExamStatus.open,
            )
        )
        s.commit()

    # 5. 启动 app
    app = create_app()
    client = TestClient(app)
    return client, SessionLocal, engine


# ---------- 单步函数 ----------


def step_health(client) -> Step:
    """1. 健康检查。"""
    h = client.get("/healthz")
    r = client.get("/readyz")
    if h.status_code == 200 and r.status_code == 200:
        return Step("health", True, "/healthz + /readyz 均 200")
    return Step("health", False, f"health={h.status_code} ready={r.status_code}")


def step_list_exams(client) -> Step:
    """2. 考试目录：list + detail。"""
    r = client.get("/api/exams")
    if r.status_code != 200 or not r.json().get("ok"):
        return Step("list_exams", False, f"list status={r.status_code}")
    body = r.json()["data"]
    items = body.get("items", [])
    if len(items) < 1:
        return Step("list_exams", False, "list 返回为空")
    exam_id = items[0]["id"]
    d = client.get(f"/api/exams/{exam_id}")
    if d.status_code != 200:
        return Step("list_exams", False, f"detail status={d.status_code}")
    return Step("list_exams", True, f"{len(items)} 条 / detail id={exam_id}")


def step_register_login(client) -> Step:
    """3. 用户注册 + 登录。"""
    email = "smoke@example.com"
    pwd = "password123"
    r1 = client.post("/api/account/register", json={"email": email, "password": pwd})
    if r1.status_code != 200:
        return Step("register_login", False, f"register={r1.status_code}")
    r2 = client.post("/api/account/login", json={"email": email, "password": pwd})
    if r2.status_code != 200 or not r2.json().get("ok"):
        return Step("register_login", False, f"login={r2.status_code}")
    token = r2.json()["data"]["token"]
    if not token:
        return Step("register_login", False, "登录未返回 token")
    return Step("register_login", True, f"token len={len(token)}")


def _create_and_confirm(client, exam_id: int) -> tuple[str, str]:
    """辅助：创建订阅 + 确认，返回 (sub_id, cancel_url)。

    confirm_url / cancel_url 形式为 /c/<token> / /s/<token>；
    confirm 端点本身是 GET /api/subscriptions/confirm?token=...。
    """
    r = client.post(
        "/api/subscriptions",
        json={
            "exam_id": exam_id,
            "email": "sub@example.com",
            "phone": "13800138000",
            "level": "standard",
            "channels": ["email"],
        },
    )
    if r.status_code != 200:
        raise RuntimeError(f"subscribe status={r.status_code} body={r.text}")
    data = r.json()["data"]
    # confirm_url 形如 /c/<token> → 取出末尾 token
    token = data["confirm_url"].rsplit("/", 1)[-1]
    confirm = client.get(
        "/api/subscriptions/confirm", params={"token": token}
    )
    if confirm.status_code != 200:
        raise RuntimeError(f"confirm status={confirm.status_code} body={confirm.text}")
    return data["subscription_id"], data["cancel_url"]


def step_subscribe_confirm(client) -> Step:
    """4. 创建订阅 + 确认。"""
    r = client.get("/api/exams")
    exam_id = r.json()["data"]["items"][0]["id"]
    try:
        sub_id, _ = _create_and_confirm(client, exam_id)
    except RuntimeError as e:
        return Step("subscribe_confirm", False, str(e))
    return Step("subscribe_confirm", True, f"sub_id={sub_id}")


def step_trigger_node(SessionLocal) -> Step:
    """5. 推进时间 + scan_now() + 验证 NotificationLog 已生成。"""
    from freezegun import freeze_time
    from sqlalchemy import select

    from app.repository.models import Exam, Subscription
    from app.repository.notification_log_repo import NotificationLogRepository
    from app.repository.orm import NodeType
    from app.scheduler.node_scanner import scan_now

    # 找到刚才那条订阅 + 关联的考试时间（单次会话内 join 取出避免 detached）
    with SessionLocal() as s:  # type: ignore[call-arg]
        row = (
            s.execute(
                select(Subscription.exam_id, Exam.registration_start)
                .join(Exam, Exam.id == Subscription.exam_id)
            )
            .first()
        )
    if row is None:
        return Step("trigger_node", False, "未找到订阅")
    # standard 档 registration_start 节点提前 1 天触发，所以冻在 reg_start - 1d
    target_time = row.registration_start - timedelta(days=1)
    sub_exam_id = row.exam_id

    with freeze_time(target_time):
        scan_now(SessionLocal)

    # 检查 NotificationLog
    from app.repository.models import NotificationLog

    with SessionLocal() as s:  # type: ignore[call-arg]
        logs = (
            s.execute(select(NotificationLog)).scalars().all()
        )
    if len(logs) < 1:
        return Step("trigger_node", False, "未生成 NotificationLog")
    relevant = [
        l for l in logs
        if getattr(l, "node_type", None) in (
            NodeType.registration_start,
            NodeType.registration_start.value,
        )
    ]
    return Step(
        "trigger_node",
        True,
        f"{len(logs)} 条日志（含 {len(relevant)} 条 registration_start）",
    )


def step_cancel(SessionLocal, client) -> Step:
    """6. 取消订阅。"""
    from sqlalchemy import select

    from app.repository.models import Subscription
    from app.repository.orm import SubscriptionStatus

    with SessionLocal() as s:  # type: ignore[call-arg]
        sub = s.execute(select(Subscription)).scalars().first()
    if sub is None:
        return Step("cancel", False, "未找到订阅")
    # 重新签发一个 cancel_token
    from app.domain.tokens import sign

    cancel_token = sign({"action": "cancel", "sub_id": sub.id}, ttl_days=30)
    r = client.post(
        "/api/subscriptions/cancel", json={"token": cancel_token}
    )
    if r.status_code != 200:
        return Step("cancel", False, f"status={r.status_code} body={r.text}")
    # 校验 status=cancelled
    with SessionLocal() as s:  # type: ignore[call-arg]
        sub2 = s.execute(select(Subscription)).scalars().first()
    if sub2.status != SubscriptionStatus.cancelled:
        return Step("cancel", False, f"状态未变更为 cancelled（仍为 {sub2.status}）")
    return Step("cancel", True, f"sub_id={sub2.id} → cancelled")


def step_change_email(client) -> Step:
    """7. 邮箱迁移（密码确认 + 新邮箱验证）。"""
    email = "smoke@example.com"
    pwd = "password123"
    r = client.post("/api/account/login", json={"email": email, "password": pwd})
    token = r.json()["data"]["token"]
    r1 = client.post(
        "/api/account/change-email",
        json={"new_email": "new-smoke@example.com", "current_password": pwd},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r1.status_code != 200:
        return Step("change_email", False, f"initiate={r1.status_code}")
    change_token = r1.json()["data"]["dev_token"]
    if not change_token:
        return Step("change_email", False, "未返回 dev_token")
    r2 = client.get(
        "/api/account/change-email/verify", params={"token": change_token}
    )
    if r2.status_code != 200 or r2.json()["data"].get("email") != "new-smoke@example.com":
        return Step("change_email", False, f"verify={r2.status_code} body={r2.text}")
    return Step("change_email", True, "old@example.com → new-smoke@example.com")


def step_dashboard(client) -> Step:
    """8. 管理后台：登录 + dashboard overview。"""
    admin_pwd = "adminpass123"  # 与 _make_app 中 bcrypt 明文保持一致
    r = client.post(
        "/api/manage/login",
        json={"username": "admin", "password": admin_pwd},
    )
    if r.status_code != 200:
        return Step("dashboard", False, f"login={r.status_code}")
    admin_token = r.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {admin_token}"}
    overview = client.get(
        "/api/manage/dashboard/overview", headers=headers
    )
    if overview.status_code != 200:
        return Step("dashboard", False, f"overview={overview.status_code}")
    return Step("dashboard", True, f"overview status=200")


# ---------- 编排 ----------


def run_all(*, fail_fast: bool = False) -> List[Step]:
    """按顺序跑完所有步骤。"""
    client, SessionLocal, _ = _make_app_and_session_factory()
    steps: List[Step] = []

    def _run(name: str, fn: Callable[[], Step]) -> None:
        s = fn()
        steps.append(s)
        if fail_fast and not s.ok:
            raise SystemExit(1)

    _run("health", lambda: step_health(client))
    _run("list_exams", lambda: step_list_exams(client))
    _run("register_login", lambda: step_register_login(client))
    _run("subscribe_confirm", lambda: step_subscribe_confirm(client))
    _run("trigger_node", lambda: step_trigger_node(SessionLocal))
    _run("cancel", lambda: step_cancel(SessionLocal, client))
    _run("change_email", lambda: step_change_email(client))
    _run("dashboard", lambda: step_dashboard(client))

    client.close()
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description="kaoshile 端到端冒烟脚本")
    parser.add_argument(
        "--fail-fast", action="store_true", help="任一步失败立即退出 1"
    )
    args = parser.parse_args()
    steps = run_all(fail_fast=args.fail_fast)
    print()
    for s in steps:
        print(s.render())
    passed = sum(1 for s in steps if s.ok)
    total = len(steps)
    print()
    print(f"汇总：{passed}/{total} 通过")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())