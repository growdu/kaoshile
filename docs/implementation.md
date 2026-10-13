# 实现方案 — 考试通知软件

> 版本：v0.1（2026-10-13）
> 对应需求：[requirements.md](./requirements.md)
> 对应设计：[design.md](./design.md)

---

## 0. 阅读须知

本方案是**研发执行手册**。任何代码变更前，请先：

1. 确认 `requirements.md` 与 `design.md` 仍然适用；
2. 在本文档找到对应章节，按「开发节奏」一节规则 commit + 配套测试；
3. 不在本文档覆盖的临时决策，需在本文档末尾「过程记录」追加一条，并随下次 commit 提交。

---

## 1. 里程碑拆分（按 commit 节奏）

> 严格遵循用户偏好：**每个子模块完成立即 commit，且必须配套单元 + 集成测试并通过**。

| # | 里程碑 | 子模块 / 提交单元 | 验收 |
| --- | --- | --- | --- |
| **M0** | 项目脚手架 | pyproject / 目录骨架 / 配置层 / 日志 / db 启动 / 健康检查 | `pytest` 空跑通过；`/healthz` 200 |
| **M1** | 数据层 | SQLAlchemy 模型 + Alembic 初始迁移 | `pytest` 通过；`alembic upgrade head` 成功 |
| **M2** | 领域层 | `reminder_policy.compute_send_times` + `tokens` 模块 | 单元测试覆盖 3 档位 + token 签发/校验 |
| **M3** | 通知通道抽象 | `Channel` Protocol + `MockChannel` + 工厂 | 单元测试覆盖 happy / retry / final-fail |
| **M4** | 考试目录 API | `GET /api/exams` + `GET /api/exams/{id}` | 集成测试覆盖过滤、分页、空态 |
| **M5** | 订阅用例 + API | `POST /api/subscriptions` + 确认页 | 集成测试覆盖 pending → active；确认邮件 / 短信已 Mock 接收 |
| **M6** | 退订用例 + API | `POST /api/subscriptions/cancel` + 退订落地页 | 集成测试覆盖 token 失效、重复退订 |
| **M7** | 调度器 + 通知扇出 | `node_scanner` + `NotificationService.dispatch` + 重试 | 集成测试用 freezegun 触发节点，断言 Mock 通道调用次数 |
| **M8** | 我的订阅页 + token 访问 | `GET /api/subscriptions/me` + 通知历史列表 | 集成测试覆盖鉴权失败、成功列表 |
| **M9** | 管理员后台 | 登录 + 考试 CRUD + 订阅 / 日志查询 | 集成测试覆盖鉴权 + 各 CRUD |
| **M10** | 阿里云真实通道 | `EmailAliyunChannel` + `SmsAliyunChannel` | 联通性脚本成功发送测试邮件 / 短信（沙箱） |
| **M11** | 模板渲染 + 文案 | 邮件 / 短信模板渲染（含退订链接） | 模板单测覆盖占位符替换 |
| **M12** | Docker / 部署脚本 | Dockerfile + docker-compose + nginx 配置示例 | `docker build` 成功；`docker run` 起服务 |
| **M13** | 灌入 demo 数据 | `scripts/seed_demo.py`（≥ 3 场考试、≥ 5 条订阅） | 手动跑一遍主链路 |
| **M14** | PII 清理 job | `cleanup.py` + 调度接入 | 集成测试覆盖 7 天后清理 |

每个里程碑**至少 1 个 commit**，每个 commit 必须配套：

- 单元测试（新增模块全覆盖）；
- 若含 API/调度变更，必须含集成测试；
- commit message 形如：`M2: 实现 reminder_policy 提前量档位计算（含单测）`。

---

## 2. 初始化（里程碑 M0）

### 2.1 命令清单

```bash
# 初始化项目
uv init --no-readme .            # 或使用 poetry / pip-tools
uv add fastapi uvicorn[standard]
uv add sqlalchemy alembic pydantic pydantic-settings
uv add apscheduler httpx structlog python-dotenv
uv add bcrypt itsdangerous
uv add aliyun-python-sdk-core aliyun-python-sdk-dm alibabacloud_dysmsapi20170525
uv add --dev pytest pytest-asyncio httpx freezegun ruff mypy

git init   # 如未初始化
```

### 2.2 目录骨架

```
app/
  __init__.py
  main.py             # FastAPI 实例 + lifespan
  config.py           # pydantic-settings
  api/__init__.py
  api/public.py
  api/manage.py
  api/deps.py
  usecase/__init__.py
  domain/__init__.py
  repository/__init__.py
  notification/__init__.py
  scheduler/__init__.py
  infra/__init__.py
  infra/db.py
  infra/logging.py
  infra/time.py
tests/
  __init__.py
  conftest.py
  unit/__init__.py
  integration/__init__.py
scripts/
migrations/           # alembic init
```

### 2.3 `app/main.py` 骨架

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.infra.logging import configure_logging
from app.infra.db import init_db
from app.scheduler.scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(lifespan=lifespan)

@app.get("/healthz")
def healthz():
    return {"ok": True}
```

### 2.4 `pyproject.toml` 关键字段

```toml
[project]
name = "kaoshile"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.27",
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "pydantic>=2.6",
  "pydantic-settings>=2.2",
  "apscheduler>=3.10",
  "httpx>=0.27",
  "structlog>=24.1",
  "bcrypt>=4.1",
  "itsdangerous>=2.1",
  "aliyun-python-sdk-core>=1.0",
  "aliyun-python-sdk-dm>=1.0",
  "alibabacloud_dysmsapi20170525>=2.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 3. 数据层（M1）

### 3.1 模型（`app/repository/orm.py`）

```python
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, Enum, ForeignKey, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum

class Base(DeclarativeBase): pass

class ExamStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    registration_closed = "registration_closed"
    archived = "archived"

class SubscriptionStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    cancelled = "cancelled"

class Exam(Base):
    __tablename__ = "exam"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))
    organizer: Mapped[str | None] = mapped_column(String(200))
    registration_start: Mapped[datetime]
    registration_end: Mapped[datetime]
    payment_end: Mapped[datetime | None]
    admission_ticket_start: Mapped[datetime | None]
    exam_date: Mapped[datetime]
    official_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ExamStatus] = mapped_column(Enum(ExamStatus))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_exam_status_reg_end", "status", "registration_end"),
    )

class Subscription(Base):
    __tablename__ = "subscription"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exam.id"))
    email: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20))
    reminder_level: Mapped[str] = mapped_column(String(20), default="standard")
    channels: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus))
    confirm_token: Mapped[str] = mapped_column(String(200), unique=True)
    cancel_token: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime]
    confirmed_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("email", "exam_id", "status", name="uq_sub_email_exam_status"),
        Index("ix_sub_email_status", "email", "status"),
        Index("ix_sub_exam_status", "exam_id", "status"),
    )

class NotificationLog(Base):
    __tablename__ = "notification_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("subscription.id"))
    exam_id: Mapped[int] = mapped_column(ForeignKey("exam.id"))
    node_type: Mapped[str] = mapped_column(String(40))
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    attempt_count: Mapped[int] = mapped_column(default=0)
    vendor_receipt_id: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("subscription_id", "node_type", "channel",
                         name="uq_log_sub_node_channel"),
    )
```

### 3.2 Alembic

```bash
alembic init -t async migrations  # 或默认模板
# 编辑 alembic.ini sqlalchemy.url = DATABASE_URL
# 第一次迁移
alembic revision --autogenerate -m "M1 init schema"
alembic upgrade head
```

### 3.3 Repository 层契约（`app/repository/subscription_repo.py`）

```python
class SubscriptionRepo:
    def __init__(self, session: Session): ...
    def insert(self, sub: Subscription) -> None: ...
    def find_by_confirm_token(self, token: str) -> Subscription | None: ...
    def find_by_cancel_token(self, token: str) -> Subscription | None: ...
    def find_active_for_node(self, node_type: str, window_start, window_end) -> list[Subscription]: ...
    def list_for_email(self, email: str) -> list[Subscription]: ...
```

---

## 4. 领域层（M2）

### 4.1 `app/domain/reminder_policy.py`

```python
from datetime import datetime, timedelta
from app.infra.time import TZ_SHANGHAI

POLICY: dict[str, dict[str, list[timedelta]]] = {
    "conservative": {
        "registration_start": [timedelta(days=-1)],
        "registration_end":   [timedelta(days=-1)],
        "payment_end":        [timedelta(days=-1)],
        "admission_start":    [timedelta(days=-1)],
        "exam_day":           [timedelta(days=-3)],
    },
    "standard": {
        "registration_start": [timedelta(days=-1)],
        "registration_end":   [timedelta(days=-3), timedelta(days=-1)],
        "payment_end":        [timedelta(days=-3), timedelta(days=-1)],
        "admission_start":    [timedelta(days=-1)],
        "exam_day":           [timedelta(days=-7), timedelta(days=-3), timedelta(days=-1)],
    },
    "aggressive": {  # ... 详见 requirements §4.3
        ...
    },
}

NODE_FIELD: dict[str, str] = {
    "registration_start": "registration_start",
    "registration_end":   "registration_end",
    "payment_end":        "payment_end",
    "admission_start":    "admission_ticket_start",
    "exam_day":           "exam_date",
}

def compute_send_times(exam: dict, level: str) -> dict[str, list[datetime]]:
    """返回每个节点对应的发送时刻（Asia/Shanghai tz-aware）。"""
    out: dict[str, list[datetime]] = {}
    policy = POLICY[level]
    for node, offsets in policy.items():
        field = NODE_FIELD[node]
        base = exam[field]
        if base is None:
            continue
        out[node] = [(base + off).astimezone(TZ_SHANGHAI) for off in offsets]
    return out
```

### 4.2 `app/domain/tokens.py`

```python
import hmac, hashlib, base64, json, time
from app.config import settings

def _b64u(b: bytes) -> str: return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def _b64u_decode(s: str) -> bytes: return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def sign(payload: dict, ttl_days: int = 30) -> str:
    payload = {**payload, "exp": int(time.time()) + ttl_days * 86400}
    body = _b64u(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    sig = hmac.new(settings.link_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"

def verify(token: str) -> dict:
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(settings.link_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise InvalidToken("bad signature")
    payload = json.loads(_b64u_decode(body))
    if payload["exp"] < int(time.time()):
        raise InvalidToken("expired")
    return payload

class InvalidToken(Exception): pass
```

---

## 5. 通知通道（M3 / M10）

### 5.1 抽象（`app/notification/base.py`）

```python
from dataclasses import dataclass
from typing import Protocol

@dataclass
class SendResult:
    success: bool
    vendor_receipt_id: str | None = None
    error: str | None = None

class Channel(Protocol):
    name: str
    def send(self, recipient: str, subject: str, body: str) -> SendResult: ...
```

### 5.2 Mock 实现（始终在仓库内，用于测试与本地）

```python
class MockChannel:
    def __init__(self, name: str = "mock", fail_times: int = 0):
        self.name = name
        self.fail_times = fail_times
        self.calls: list[tuple[str, str, str]] = []
        self._sent_count = 0

    def send(self, recipient, subject, body) -> SendResult:
        self.calls.append((recipient, subject, body))
        self._sent_count += 1
        if self._sent_count <= self.fail_times:
            return SendResult(False, error="mock transient failure")
        returnResult.success = True
        return SendResult(True, vendor_receipt_id=f"mock-{self._sent_count}")
```

### 5.3 阿里云邮件（M10）

```python
# 仅勾勒，依赖官方 SDK
from aliyunsdkcore.client import AcsClient
from aliyunsdkdm.request.v20151123 import SingleSendMailRequest

class EmailAliyunChannel:
    name = "email_aliyun"
    def __init__(self, access_key: str, secret: str, region: str,
                 account_name: str, from_alias: str):
        self.client = AcsClient(access_key, secret, region)
        self.account_name = account_name
        self.from_alias = from_alias

    def send(self, recipient, subject, body) -> SendResult:
        req = SingleSendMailRequest()
        req.set_AccountName(self.account_name)
        req.set_FromAlias(self.from_alias)
        req.set_AddressType(1)
        req.set_ToAddress(recipient)
        req.set_Subject(subject)
        req.set_HtmlBody(body)
        try:
            resp = self.client.do_action_with_exception(req)
            return SendResult(True, vendor_receipt_id=_extract_id(resp))
        except Exception as e:
            return SendResult(False, error=str(e))
```

### 5.4 阿里云短信（M10）

```python
from alibabacloud_dysmsapi20170525.client import Client as SmsClient
from alibabacloud_dysmsapi20170525 import models as sms_models
from alibabacloud_tea_openapi import models as open_api_models

class SmsAliyunChannel:
    name = "sms_aliyun"
    def __init__(self, access_key, secret, sign_name, template_code):
        cfg = open_api_models.Config(access_key_id=access_key, access_key_secret=secret)
        cfg.endpoint = "dysmsapi.aliyuncs.com"
        self.client = SmsClient(cfg)
        self.sign_name = sign_name
        self.template_code = template_code

    def send(self, recipient, subject, body) -> SendResult:
        # SMS 中 subject 被丢弃，body 作为模板变量传入
        try:
            req = sms_models.SendSmsRequest(
                phone_numbers=recipient, sign_name=self.sign_name,
                template_code=self.template_code, template_param=json.dumps({"content": body}),
            )
            resp = self.client.send_sms(req)
            if resp.body.code == "OK":
                return SendResult(True, vendor_receipt_id=resp.body.request_id)
            return SendResult(False, error=resp.body.message)
        except Exception as e:
            return SendResult(False, error=str(e))
```

---

## 6. 用例层（M5 / M6 / M7）

### 6.1 `app/usecase/subscription.py` 骨架

```python
class SubscriptionService:
    def __init__(self, sub_repo, log_repo, channels: dict[str, Channel],
                 clock=now_utc):
        self.sub_repo = sub_repo
        self.log_repo = log_repo
        self.channels = channels
        self.clock = clock

    def create(self, exam_id, email, phone, level, channels):
        # 1. 校验 exam 存在且 status=open
        # 2. 校验 email/phone 格式
        # 3. 校验 channels ∈ {email, sms}
        # 4. 计算 send_times（reminder_policy）
        # 5. 生成 confirm_token / cancel_token（tokens.sign）
        # 6. insert subscription status=pending
        # 7. 异步发送确认通知（mock 同步亦可）
        ...
```

### 6.2 `app/usecase/notification.py` 骨架

```python
class NotificationService:
    def __init__(self, log_repo, channels, clock=now_utc, max_attempts=3):
        self.log_repo = log_repo
        self.channels = channels
        self.clock = clock
        self.max_attempts = max_attempts

    def dispatch(self, subscription, node_type, channel_name, subject, body):
        # 1. 查 log 是否已 sent（幂等）
        # 2. 调 channel.send，指数退避重试至 max_attempts
        # 3. 写 log（success / failed）
        # 4. 返回 SendResult
        ...
```

---

## 7. 调度层（M7）

### 7.1 `app/scheduler/node_scanner.py`

```python
from datetime import timedelta
from app.infra.time import now_shanghai, TZ_SHANGHAI

WINDOW = timedelta(minutes=1)

def scan_now(session_factory, sub_repo, log_repo, notification_service):
    """每分钟调用一次：发现该触发的 (subscription, node, channel) 三元组。"""
    now = now_shanghai()
    window_start = now - WINDOW
    window_end = now
    # 1. 对每个节点类型，查 active 订阅（exam 的对应字段落在 [window_start, window_end]）
    # 2. 对每条订阅，按其 reminder_level 推导所有触发时刻，匹配当前窗口
    # 3. 调 notification_service.dispatch(...)
```

### 7.2 `app/scheduler/scheduler.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

_scheduler: AsyncIOScheduler | None = None

def start_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(scan_now, "cron", minute="*", id="node_scanner",
                       replace_existing=True, max_instances=1, coalesce=True)
    _scheduler.start()

def stop_scheduler():
    if _scheduler:
        _scheduler.shutdown(wait=False)
```

---

## 8. API 层（M4 / M5 / M6 / M8 / M9）

### 8.1 `app/api/public.py`

```python
from fastapi import APIRouter, Depends, HTTPException
router = APIRouter()

@router.get("/api/exams")
def list_exams(q: str | None = None, category: str | None = None,
               status: str | None = None, ...): ...

@router.get("/api/exams/{exam_id}")
def get_exam(exam_id: int): ...

@router.post("/api/subscriptions")
async def create_subscription(payload: CreateSubscriptionIn): ...

@router.get("/api/subscriptions/confirm")
def confirm_subscription(token: str): ...

@router.post("/api/subscriptions/cancel")
async def cancel_subscription(payload: CancelIn): ...

@router.get("/api/subscriptions/me")
def my_subscriptions(email: str, token: str): ...

@router.get("/c/{token}")
def confirm_page(token: str): ...   # 渲染 HTML
@router.get("/s/{token}")
def cancel_page(token: str): ...
```

### 8.2 错误响应统一信封

```python
# app/api/deps.py
def ok(data): return {"ok": True, "data": data}
def err(code, message): return {"ok": False, "error": {"code": code, "message": message}}
```

---

## 9. 测试策略（M0 起全程）

### 9.1 测试金字塔

- **单元测试**（`tests/unit/`）：覆盖 `domain/` 全部、`usecase/` 全部（fake repo）、`notification/` 全部（mock 通道）；
- **集成测试**（`tests/integration/`）：FastAPI TestClient + 真实 SQLite（tempfile）+ Mock 通道；覆盖每个 API happy path 与主要失败路径；
- **调度测试**：`freezegun` 冻结时间，手动调用 `scan_now`，断言 Mock 通道接收到的调用。

### 9.2 共用 fixture（`tests/conftest.py`）

```python
@pytest.fixture
def session(): ...              # 临时 SQLite
@pytest.fixture
def mock_email() -> MockChannel: ...
@pytest.fixture
def mock_sms() -> MockChannel: ...
@pytest.fixture
def client(session, mock_email, mock_sms): ...   # TestClient with overrides
@pytest.fixture
def frozen_clock(): ...          # freezegun
```

### 9.3 每个里程碑必跑的测试清单

| 里程碑 | 必须覆盖 |
| --- | --- |
| M0 | `/healthz` 返回 200；logger 输出结构化字段 |
| M1 | 模型字段映射；Alembic 升级可逆 |
| M2 | 3 档位 × 5 节点 = 15 种 send_times；token 签发 / 校验 / 过期 / 篡改 |
| M3 | 0/1/3 次失败下的 SendResult；不可重试错误立即返回 |
| M4 | 列表过滤、分页、空态；详情 404 |
| M5 | 创建后返回 pending；确认后 active；确认 token 错误 400 |
| M6 | 退订成功；重复退订幂等；过期 token 400 |
| M7 | freezegun 触发 1 个考试 5 个节点共 N 次发送；1 次失败重试通过 |
| M8 | 错误 token 401；正确 token 列出订阅 |
| M9 | 鉴权失败；考试 CRUD；订阅 / 日志查询过滤 |
| M10 | 真实通道联通性脚本（手动） |
| M11 | 模板占位符替换；退订链接存在 |
| M12 | `docker build` 成功；容器内 `/healthz` 200 |
| M14 | 7 天后 PII 字段被 NULL 化 |

### 9.4 覆盖率门槛

- 单元测试行覆盖 ≥ 80%；
- 关键模块（`reminder_policy`、`tokens`、`notification_service`、`subscription_service`）必须 100% 行覆盖；
- CI（v1.1 引入）阻断覆盖率下降。

---

## 10. 开发节奏（**强约束**）

> 来源：用户长期偏好（已写入 user memory）。
> 适用：本次项目以及任何后续多 commit / 强测试要求的开发任务。

### 10.1 规则

1. **每个子模块完成立即 commit**——不攒 commit；
2. **每个 commit 必须配套**：
   - 新模块的单元测试（happy + 至少 1 个失败路径）；
   - 若引入 / 修改 API 或调度行为，对应的集成测试；
   - 所有新增测试在本地 `pytest` 全绿；
3. **代码可测试、可回溯、简单易懂**：
   - 单文件不超过 ~300 行（超过即拆）；
   - 函数不超过 ~50 行（超过即拆）；
   - 函数最多 3 层缩进；
   - 每个 PR / commit 描述包含「为什么」与「测试覆盖了什么」；
4. **不允许跳过测试**——`pytest --maxfail=1` 通过才能 commit。

### 10.2 commit message 模板

```
M{里程碑号}: {一句话变更}

- {变更点 1}
- {变更点 2}
- 测试: {新增/修改的测试点}
```

示例：

```
M2: 实现 reminder_policy 提前量档位计算（含单测）

- 新增 app/domain/reminder_policy.py，提供 compute_send_times
- POLICY 矩阵覆盖 conservative/standard/aggressive 三档
- 测试: tests/unit/test_reminder_policy.py 覆盖 3 档位 × 5 节点
```

---

## 11. 验证与发布

### 11.1 本地验证

```bash
uv run pytest -q                      # 全测试
uv run pytest --cov=app --cov-report=term-missing  # 覆盖率
uv run alembic upgrade head            # 迁移
uv run python scripts/seed_demo.py     # 灌入 demo
uv run uvicorn app.main:app --reload   # 启动
curl http://localhost:8000/healthz     # 健康检查
```

### 11.2 阿里云联通性

```bash
uv run python scripts/send_test_email.py  # 发一封测试邮件
uv run python scripts/send_test_sms.py    # 发一条测试短信
```

### 11.3 端到端冒烟

1. 浏览器打开首页，确认考试目录展示；
2. 选一场考试 → 订阅 → 邮箱收到确认链接 → 点击 → 状态变 active；
3. `pytest tests/integration/test_scheduler_e2e.py` 用 freezegun 跳到节点时刻，断言 Mock 通道收到对应发送；
4. 邮件中点退订 → 订阅 cancelled；
5. 管理员后台登录 → 看订阅列表、看发送日志、看失败记录。

---

## 12. 验收检查清单（与 `requirements.md §8` 对齐）

- [ ] 全部 P0 / P1 功能项实现并通过测试；
- [ ] 每个 commit 配套单测 + 集测（参见 §1 里程碑列表）；
- [ ] 主链路「订阅 → 确认 → 节点到达 → 收到通知 → 退订」跑通；
- [ ] 阿里云两个通道均能发送真实邮件 + 短信（带脱敏收件人）；
- [ ] 失败路径正确重试并标记失败；
- [ ] README / 设计 / 实现文档与代码一致；
- [ ] demo 数据：≥ 3 场考试 + ≥ 5 条订阅；
- [ ] `pytest` 在本地 CI 容器内全绿；
- [ ] `docker build` 成功，容器内服务可达。

---

## 13. 过程记录

> 在实现过程中如发现文档与现实不符、需要做临时决策，请在此追加。提交 PR 时将本节增量同步进对应章节。

| 日期 | 决策 | 影响 | 提出人 |
| --- | --- | --- | --- |
| 2026-10-13 | 选用 FastAPI + APScheduler 单体起步 | 锁定 v1 架构 | Mavis |
| 2026-10-13 | 通知通道抽象为 Protocol | 允许 mock + 未来加微信 | Mavis |

---

> 文档结束。任何实现变动请同步更新本文档并升级版本号。
