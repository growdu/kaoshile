# 设计文档 — 考试通知软件

> 版本：v0.1（2026-10-13）
> 对应需求：[requirements.md](./requirements.md)

---

## 1. 架构概览

```
┌──────────────────────────────────────────────────────────────────┐
│                          浏览器（Web SPA）                       │
│  考试目录 / 考试详情 / 订阅表单 / 我的订阅 / 退订落地页           │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTPS / JSON
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Web 服务（FastAPI）                          │
│  · REST API                                                       │
│  · 鉴权中间件（管理员） / HMAC token 校验（用户）                  │
│  · 业务用例编排（订阅 / 退订 / 通知触发）                         │
│  · Jinja2 服务端渲染（订阅确认 / 退订落地页，可选）                │
└──────────────┬─────────────────────────┬─────────────────────────┘
               │                         │
               ▼                         ▼
       ┌───────────────────┐   ┌──────────────────────────┐
       │  数据层           │   │  调度器（APScheduler）    │
       │  SQLAlchemy ORM   │   │  · 每分钟扫描到期节点     │
       │  SQLite (dev)     │   │  · 加载活跃订阅           │
       │  PostgreSQL(prod) │   │  · 调通知发送器扇出        │
       │  Alembic 迁移     │   │  · 持久化作业状态          │
       └───────────────────┘   └──────────┬───────────────┘
                                          │
                                          ▼
                          ┌──────────────────────────────┐
                          │  通知发送层（Channel 抽象）    │
                          │  · EmailChannel（阿里云 DM）  │
                          │  · SmsChannel（阿里云 SMS）   │
                          │  · MockChannel（测试用）       │
                          └──────────────────────────────┘
                                          │
                                          ▼
                          ┌──────────────────────────────┐
                          │  阿里云 DirectMail / SMS API │
                          └──────────────────────────────┘
```

**架构要点**：

- **单体起步，按需拆**：v1 所有模块同进程；调度器与 Web API 之间通过**内存事件总线**解耦（同一进程内简单 `asyncio.Queue`），后续可拆为独立 Worker，零业务改动；
- **通道可插拔**：通知发送层只暴露抽象接口，新增通道不动业务代码；
- **数据层与领域解耦**：所有数据库访问集中在 `repository/` 层，业务层通过用例（`usecase/`）编排，不直接写 ORM；
- **时区统一**：所有 datetime 字段在数据库层使用 UTC，应用层统一转换到 `Asia/Shanghai` 展示与判定。

---

## 2. 技术栈选型

### 2.1 推荐栈

| 层 | 选型 | 理由 |
| --- | --- | --- |
| 语言 | **Python 3.11+** | 阿里云官方 SDK 完整、生态成熟、调试门槛低 |
| Web 框架 | **FastAPI** | 异步友好、自动 OpenAPI、Pydantic 模型天然契合需求模型 |
| ORM | **SQLAlchemy 2.x（同步即可）** | v1 流量小，同步代码可读性更好；后续可换 async |
| 数据库 | **SQLite（开发）/ PostgreSQL（生产）** | SQLite 单文件零运维适合 v1，PG 适合后续多实例 |
| 迁移 | **Alembic** | SQLAlchemy 官方迁移工具 |
| 调度 | **APScheduler（AsyncIOScheduler）** | 进程内调度足够 v1，API 简洁；后续可换 Celery / Argo |
| 配置 | **pydantic-settings + .env** | 类型安全的配置层 |
| 邮件 SDK | **阿里云 DirectMail SDK（aliyun-python-sdk-dm）** | 官方 SDK |
| 短信 SDK | **阿里云 SMS SDK（aliyun-python-sdk-core + dysmsapi）** | 官方 SDK |
| HTTP 客户端 | **httpx** | 异步、可 mock |
| 测试 | **pytest + pytest-asyncio + httpx + freezegun** | 时间冻结对调度测试至关重要 |
| 部署 | **Docker（单容器起步）** | 后续拆 Worker 时无需重写 |
| 日志 | **structlog** | 结构化、易聚合 |

### 2.2 拒绝的替代方案与理由

| 候选 | 拒绝理由 |
| --- | --- |
| Django | 自带 admin 诱人但 ORM/模板与 FastAPI 异步栈不契合；通知调度需额外接 Celery |
| Celery | v1 单实例无必要；增加 broker 依赖 |
| Node.js（NestJS） | 阿里云 SDK 也成熟，但 Python 在模板渲染与运维脚本上更顺手 |
| Go | 性能 / 部署优势对 v1 不重要；开发节奏反而更慢 |

---

## 3. 目录结构

```
kaoshile/
├── docs/                       # 本目录
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # pydantic-settings 配置
│   ├── api/                    # 路由层
│   │   ├── public.py           # 考试目录 / 订阅 / 退订
│   │   ├── manage.py           # 管理员后台
│   │   └── deps.py             # 鉴权依赖
│   ├── usecase/                # 业务用例
│   │   ├── subscription.py
│   │   ├── notification.py
│   │   └── exam.py
│   ├── domain/                 # 领域模型 + 纯函数
│   │   ├── models.py           # Pydantic / dataclass
│   │   ├── reminder_policy.py  # 提前量档位计算
│   │   └── tokens.py           # HMAC token
│   ├── repository/             # 数据访问
│   │   ├── exam_repo.py
│   │   ├── subscription_repo.py
│   │   └── notification_log_repo.py
│   ├── notification/           # 通知通道抽象与实现
│   │   ├── base.py             # Channel 抽象
│   │   ├── email_aliyun.py
│   │   ├── sms_aliyun.py
│   │   └── templates/          # 渲染模板
│   ├── scheduler/              # APScheduler 启动与扫描
│   │   ├── scheduler.py
│   │   └── node_scanner.py
│   ├── infra/                  # 基础设施
│   │   ├── db.py               # SQLAlchemy engine/session
│   │   ├── logging.py
│   │   └── time.py             # tz-aware 时间工具
│   └── static/                 # 前端资源
│       ├── index.html
│       ├── exam.html
│       ├── subscribe.html
│       └── manage.html
├── migrations/                 # Alembic
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── scripts/
│   ├── seed_demo.py            # 灌入 demo 数据
│   └── send_test_email.py      # 阿里云通道联通性测试
├── pyproject.toml
├── alembic.ini
├── Dockerfile
└── .env.example
```

**目录原则**：

- `usecase/` 内不放 ORM、不放 HTTP，便于单元测试与复用；
- `repository/` 只做 CRUD 与基础查询，不做业务规则；
- `notification/` 完全独立，单元测试可用 Mock，不依赖网络；
- `domain/` 内是**纯 Python 函数**（含时间计算、token 签名），不引用框架。

---

## 4. 模块划分

### 4.1 模块清单

| 模块 | 职责 | 关键类型 |
| --- | --- | --- |
| `api.public` | 考试目录 / 订阅 / 退订路由 | APIRouter |
| `api.manage` | 管理员 CRUD / 查询 | APIRouter |
| `usecase.subscription` | 订阅创建 / 确认 / 退订 / 修改 | SubscriptionService |
| `usecase.notification` | 通知扇出 / 重试 / 状态记录 | NotificationService |
| `usecase.exam` | 考试 CRUD 与状态机 | ExamService |
| `domain.reminder_policy` | 由档位推导每个节点的发送时刻 | pure function |
| `domain.tokens` | HMAC token 签发 / 校验 | pure function |
| `repository.*` | ORM 读写 | Repo 类 |
| `notification.*` | 通道实现 | Channel 协议 |
| `scheduler.*` | 调度扫描 | job 函数 |
| `infra.db` | engine / session / sessionmaker | — |

### 4.2 关键类型签名

```python
# domain/reminder_policy.py
NodeType = Literal["registration_start", "registration_end",
                   "payment_end", "admission_start", "exam_day"]
ReminderLevel = Literal["conservative", "standard", "aggressive"]

def compute_send_times(exam: Exam, level: ReminderLevel) -> dict[NodeType, list[datetime]]:
    """返回每个节点对应的若干发送时刻（已转 Asia/Shanghai）。"""

# notification/base.py
@dataclass
class SendResult:
    success: bool
    vendor_receipt_id: str | None
    error: str | None

class Channel(Protocol):
    name: str
    def send(self, recipient: str, subject: str, body: str) -> SendResult: ...

# usecase/subscription.py
class SubscriptionService:
    def create(self, exam_id: int, email: str, phone: str,
               level: ReminderLevel, channels: list[str]) -> Subscription: ...
    def confirm(self, token: str) -> Subscription: ...
    def cancel(self, token: str) -> Subscription: ...
    def list_for_email(self, email: str, token: str) -> list[Subscription]: ...
```

---

## 5. 数据模型

详细字段见 `requirements.md §6`，下面是关系示意与索引策略。

```
Exam 1 ──< Subscription >── 1 NotificationLog
              │                     │
              └─────────────────────┘
                  (subscription_id)
```

**索引**：

- `subscription(email, status)` — 用户查询自己的订阅；
- `subscription(exam_id, status)` — 调度扇出时的批量查询；
- `notification_log(subscription_id, node_type, channel)` 唯一约束 — 保证 idempotent；
- `exam(status, registration_end)` — 目录列表按状态过滤；
- `exam(last_verified_at)` — 复核告警 job 用。

**约束**：

- 同一 `(email, exam_id, status=active)` 不允许多条（部分唯一索引，处理时需 `INSERT ... ON CONFLICT` 或应用层判断）；
- `notification_log` 同一 `(subscription_id, node_type, channel)` 唯一。

**考试记录的额外字段**（数据可靠性相关）：

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `source_url` | string（必填） | 录入时所依据的官方公告 URL |
| `source_hash` | string | 公告正文 SHA256，用于变更检测 |
| `last_verified_at` | datetime | 上次人工复核时间 |
| `verifier` | string | 上次复核管理员账号 |

> 复核规则与告警见 `data_sources.md §4.4`。

---

## 6. API 设计

> 所有响应遵循统一信封：`{"ok": true, "data": ...}` 或 `{"ok": false, "error": {"code": "...", "message": "..."}}`。

### 6.1 公共 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/exams` | 考试目录，支持 `q`、`category`、`status` 过滤 |
| GET | `/api/exams/{id}` | 考试详情 |
| POST | `/api/subscriptions` | 创建订阅（异步发确认通知） |
| GET | `/api/subscriptions/confirm?token=...` | 确认订阅 |
| POST | `/api/subscriptions/cancel` | 退订（body: `{"token": "..."}`） |
| GET | `/api/subscriptions/me?email=&token=` | 我的订阅列表 |
| GET | `/s/{token}` | 退订落地页（HTML） |
| GET | `/c/{token}` | 确认落地页（HTML） |

### 6.2 管理员 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/manage/login` | 登录获取 session cookie |
| POST | `/api/manage/logout` | 登出 |
| GET / POST | `/api/manage/exams` | 列表 / 新建 |
| GET / PUT / DELETE | `/api/manage/exams/{id}` | 详情 / 修改 / 删除（软删） |
| GET | `/api/manage/subscriptions` | 列表，支持 `exam_id`、`status` 过滤 |
| GET | `/api/manage/notifications` | 发送日志，支持时间 / 状态过滤 |
| GET / PUT | `/api/manage/templates` | 模板查看 / 编辑 |
| GET | `/api/manage/health` | 健康信息（队列深度、最近失败数） |

### 6.3 关键请求 / 响应示例

```http
POST /api/subscriptions
Content-Type: application/json

{
  "exam_id": 12,
  "email": "user@example.com",
  "phone": "13800138000",
  "level": "standard",
  "channels": ["email", "sms"]
}
```

```json
{
  "ok": true,
  "data": {
    "subscription_id": "3f8e...",
    "status": "pending",
    "confirm_url": "/c/eyJzaWciOi...",
    "send_times": {
      "registration_end": ["2026-10-20T09:00:00+08:00", "2026-10-22T09:00:00+08:00"],
      "exam_day": ["2026-11-08T07:00:00+08:00"]
    }
  }
}
```

---

## 7. 关键流程

### 7.1 订阅流程（时序）

```
用户 → POST /api/subscriptions
  → SubscriptionService.create
      → ExamRepo.get(id)
      → ReminderPolicy.compute_send_times(exam, level)
      → SubscriptionRepo.insert(status=pending, confirm_token)
      → NotificationService.send_confirm(subscription)  // 双通道
  ← 返回 subscription_id + confirm_url

用户 → 点击确认链接 /c/{token}
  → SubscriptionService.confirm(token)
      → SubscriptionRepo.find_by_confirm_token(token)
      → SubscriptionRepo.update(status=active)
  ← 渲染确认成功页
```

### 7.2 调度与通知发送

```
APScheduler 每分钟触发 node_scanner.scan_now()

node_scanner.scan_now():
  1. now = 当前 Asia/Shanghai 时间
  2. for node_type in 所有节点:
       candidates = SubscriptionRepo.find_active_for_node(node_type, now)
         // 查询 exam.<node_field> in (now, now + 60s]
         // 且 subscription.send_times[node_type] 包含 now 时刻
       for sub in candidates:
         for channel in sub.channels:
           if NotificationLogRepo.exists(sub.id, node_type, channel):
             continue  // 幂等
           NotificationLogRepo.create(sub.id, node_type, channel, status=queued)
           queue.put_nowait(NotifyJob(sub.id, node_type, channel))

worker 异步消费 NotifyJob:
  → NotificationService.dispatch(sub, node_type, channel)
      → Channel.send(...)
      → 失败：指数退避重试，最多 3 次
      → 最终：NotificationLogRepo.update(status=sent/failed)
```

**关键决策**：

- **不直接用 APScheduler 的 `add_job` 为每条通知调度**，原因：
  1. 通知量大时 job 表膨胀，调度器扫描开销高；
  2. 多实例无法协调（v1 单实例不显式抢锁，引入**查询时刻判断**代替 lock）；
- **采用「扫描 + 队列」模式**：调度器只负责探测该触发的节点，业务扇出走内存队列，简单可测。

### 7.3 退订流程

```
用户点击通知中退订链接 /s/{token}
  → SubscriptionService.cancel(token)
      → SubscriptionRepo.find_by_cancel_token(token)
      → 校验签名 / 未过期
      → SubscriptionRepo.update(status=cancelled)
      → NotificationLogRepo.mark_skip_future_for(sub.id)  // 已排队的丢弃
  ← 渲染退订成功页
```

退订后 PII 清理由**每日清理 job** 在 `cancelled_at + 7 days` 触发执行。

---

## 8. 通知通道抽象

### 8.1 接口

```python
class Channel(Protocol):
    name: str
    def send(self, recipient: str, subject: str, body: str) -> SendResult: ...
```

### 8.2 实现

| 类 | name | 依赖 |
| --- | --- | --- |
| `EmailAliyunChannel` | `email_aliyun` | `aliyun-python-sdk-dm` |
| `SmsAliyunChannel` | `sms_aliyun` | `aliyun-python-sdk-core` + `dysmsapi` |
| `MockChannel` | `mock` | 仅测试中使用，记入内存 |

### 8.3 注册与解析

```python
# notification/registry.py
_registry: dict[str, Channel] = {}

def register(channel: Channel) -> None: ...
def get(name: str) -> Channel: ...

# main.py 启动时
register(EmailAliyunChannel(...))
register(SmsAliyunChannel(...))
```

### 8.4 失败处理

- **可重试错误**：网络超时、5xx、限流（429）→ 指数退避（1s/5s/25s）；
- **不可重试错误**：参数错误（4xx）、模板未审核通过 → 直接标记 `failed`，不再重试；
- **告警**：失败连续 ≥ 10 条 / 分钟触发结构化告警日志（v1 由日志聚合系统订阅）。

---

## 9. 调度器设计

### 9.1 APScheduler 配置

- `AsyncIOScheduler`，单实例；
- job：`node_scanner.scan_now`，cron `* * * * *`（每分钟）；
- 启动在 FastAPI `lifespan` 中；
- 优雅停止：收到 SIGTERM 后等待当前 job 跑完，再 `shutdown(wait=False)`。

### 9.2 时间判定

- 所有时间字段入库为 **UTC**；
- 业务判定用 `Asia/Shanghai` 转换（`infra/time.py` 提供 `now_shanghai()`、`to_utc(dt)`）；
- 测试用 `freezegun` 冻结时间，配合 `now_shanghai` 可重写。

### 9.3 多实例安全（v1 说明）

v1 单实例部署，扫描器对每个 `(subscription, node_type, channel)` 三元组有**唯一约束**，多实例并发扫描时数据库层面兜底幂等。v1.1 可加 Redis 锁。

---

## 10. 安全设计

### 10.1 Token

```python
# domain/tokens.py
SECRET = config.link_secret  # 32 字节随机，从环境变量注入

def sign(payload: dict) -> str:
    body = base64url(json.dumps(payload, sort_keys=True).encode())
    sig = hmac.new(SECRET, body, sha256).hexdigest()
    return f"{body}.{sig}"

def verify(token: str) -> dict:
    body, sig = token.rsplit(".", 1)
    expected = hmac.new(SECRET, body.encode(), sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise InvalidToken
    return json.loads(base64url_decode(body))
```

- payload 包含 `sub_id`、`exp`、`action`（confirm/cancel）；
- URL 中只放 token，不放 email/phone。

### 10.2 管理员鉴权

- 账号 + 密码（bcrypt 哈希入库），登录成功签发 session cookie（HttpOnly、SameSite=Lax）；
- 中间件校验 `/api/manage/*` 必须带 session；
- 登录失败 5 次锁定 15 分钟。

### 10.3 凭据管理

- 阿里云 AccessKey / SecretKey 仅从环境变量 `ALIYUN_ACCESS_KEY_ID` / `ALIYUN_ACCESS_KEY_SECRET` 读取；
- `.env.example` 提供样板，真值不入库、不入日志；
- 日志中间件自动 redact `aliyun`、`access_key`、`secret`、`phone`、`email` 等敏感字段。

---

## 11. 可测试性设计

> 严格遵循用户的开发节奏偏好：**每行代码必须可测试、可回溯、简单且易于理解**。

### 11.1 测试金字塔

```
        ╱ E2E（少量）
       ╱
      ╱  集成测试（API + DB + Mock 通道）
     ╱
    ╱  单元测试（domain / usecase 大量）
```

- **单元测试**：纯函数、usecase 用 fake repo，覆盖率目标 ≥ 80%；
- **集成测试**：FastAPI TestClient + 真 SQLite + Mock 通道，覆盖每个 API 的 happy path 与主要失败路径；
- **E2E（可选）**：本地启服务 + 真实阿里云 sandbox（仅 release 前手动跑一次）。

### 11.2 关键 Mock 点

- `Channel` 接口可被 `MockChannel` 替换，记录所有调用；
- `Clock` 抽象（`infra/time.py`）可被 `FrozenClock` 替换；
- 数据库用 SQLite `:memory:` 或临时文件，每个测试隔离。

### 11.3 测试覆盖清单（强制项）

每个新文件 / 新模块须满足：

- [ ] 至少 1 个单元测试覆盖 happy path；
- [ ] 至少 1 个单元测试覆盖主要失败路径；
- [ ] 若新增 API 端点，至少 1 个集成测试；
- [ ] 若修改调度逻辑，必须有 freezegun 时间冻结测试。

---

## 12. 部署拓扑

### 12.1 v1 单容器

```
┌────────────────────────────────┐
│  Docker container              │
│  ┌──────────┐  ┌────────────┐  │
│  │ FastAPI  │  │ APScheduler│  │
│  │  :8000   │  │ (in-proc)  │  │
│  └────┬─────┘  └─────┬──────┘  │
│       └───────┬──────┘         │
│               ▼                │
│         SQLite (volume)        │
└────────────────────────────────┘
```

- Nginx 反代 443 → 8000；
- SQLite 文件挂载在 named volume；
- 日志 stdout → 宿主机 / 日志聚合。

### 12.2 v1.1 演进

- 拆 `worker` 容器消费 `NotifyJob`（可走 Redis Streams）；
- 数据库切换 PostgreSQL；
- 调度器加 Redis 锁。

---

## 13. 配置管理

### 13.1 `.env.example`

```env
APP_ENV=dev
APP_PORT=8000
DATABASE_URL=sqlite:///./data/app.db
TIMEZONE=Asia/Shanghai
LINK_SECRET=__generate_random_32_bytes__
MANAGE_USERNAME=admin
MANAGE_PASSWORD_HASH=__bcrypt__
ALIYUN_REGION=cn-hangzhou
ALIYUN_ACCESS_KEY_ID=__from_env__
ALIYUN_ACCESS_KEY_SECRET=__from_env__
ALIYUN_DM_ACCOUNT_NAME=noreply@yourdomain.com
ALIYUN_DM_FROM_ALIAS=考试通知
ALIYUN_SMS_SIGN_NAME=__approved__
ALIYUN_SMS_TEMPLATE_CODE=__approved__
LOG_LEVEL=INFO
```

### 13.2 配置加载

`app/config.py` 使用 `pydantic-settings.BaseSettings`，启动时校验缺失关键配置并 fail-fast。

---

## 14. 风险与对策

| 风险 | 影响 | 对策 |
| --- | --- | --- |
| 阿里云模板未审核通过 | 上线阻塞 | 上线前 1 周完成报备；准备 mock fallback |
| 多实例重复发送 | 用户被打扰 | DB 唯一约束 + 单实例 v1 |
| 时间漂移导致漏发 | 错过关键节点 | 每分钟扫描、UTC 入库、tz 工具集中 |
| 短信签名合规问题 | 短信被拦截 | 上线前完成签名报备，使用阿里云官方签名 |
| 用户滥用订阅 | 阿里云通道费用飙升 | 单邮箱单考试限 1 条 active 订阅；增加速率限制 |
| 数据丢失 | 订阅 / 日志丢失 | 日备份 SQLite；生产切 PG 后由云厂商负责 |
| 调度器重启丢任务 | 错过节点 | 扫描 + 队列模式不丢；启动时立即跑一次 scan_now |
| HMAC token 泄漏 | 任意人退订 | token 中带 `exp`；过期 30 天；定期轮换 `LINK_SECRET` |
| 考试公告变更未被识别 | 用户收到过期时间提醒 | `last_verified_at` 复核 + `source_hash` 变更检测（见 `data_sources.md §5`） |
| 管理员长期不复核 | 用户看到过期数据 | 30 天告警；90 天自动 `draft` 化 |
| 误录商业认证 | 偏离产品定位 | `seed_exams.md §10` 明确不收录清单 + 解析助手分类校验 |

---

## 15. 设计原则小结

- **简单胜过聪明**：能用同步代码就不用 asyncio；能 SQLite 就不用分布式；
- **业务与基础设施解耦**：通道、数据库、时间都可替换；
- **每个模块都有测试**：不写测试的代码不允许合并；
- **文档先于代码**：本文档先稳定，再写代码。

---

> 文档结束。任何架构变动请同步更新本文档并升级版本号。
