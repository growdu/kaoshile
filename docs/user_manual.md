# 用户手册

> 项目：**kaoshile**（考试乐）— 用户订阅考试，系统在关键时间点自动通过邮件 / 短信提醒。
> 文档版本：v6.0（2026-10-14）

本文档面向两类用户：

- **普通用户**（订阅考试 / 收到提醒）：见 [§1](#1-普通用户手册)。
- **运维 / 数据管理员**（管理考试目录 / 模板 / 看板）：见 [§2](#2-管理员手册)。

所有接口统一返 JSON；HTTP 状态码约定见 [§3](#3-公共约定)。

---

## 1. 普通用户手册

### 1.1 注册账号

```
POST /api/account/register
Content-Type: application/json

{"email": "you@example.com", "password": "your-password"}
```

- 邮箱格式必须合法；密码至少 8 位；
- 注册即登录，返回用户信息和会话 token；
- 同一个邮箱不能重复注册。

### 1.2 登录获取会话 token

```
POST /api/account/login
Content-Type: application/json

{"email": "you@example.com", "password": "your-password"}
```

- 成功返回 `data.token`（1 天 TTL），后续请求通过 `Authorization: Bearer <token>` 传递；
- token 过期或密码被改后旧 token 立即失效。

### 1.3 浏览考试目录

无需登录。

```
GET /api/exams?q=软考&category=IT&status=open&offset=0&limit=20
```

- `q` 按名称子串过滤；`category` 按类别；`status=open|draft|closed`；
- 返回 `data.items`（课程简述）与 `data.total`（总数）；

```
GET /api/exams/{exam_id}
```

返回单场考试的完整时间字段（报名开始 / 截止 / 缴费 / 准考证 / 考试日）。

### 1.4 订阅一场考试

无需登录。

```
POST /api/subscriptions
Content-Type: application/json

{
  "exam_id": 12,
  "email": "you@example.com",
  "phone": "13800138000",
  "level": "standard",
  "channels": ["email", "sms"]
}
```

- `level` ∈ `conservative` / `standard` / `aggressive`（提前提醒粒度不同）；
- `channels` ∈ `email` / `sms` / `wechat` / `dingtalk` / `feishu`（不在可选范围内启用）；
- 订阅默认 `pending`，需在确认链接激活后变 `active`；
- 返回 `confirm_url`（形如 `/c/<token>`）和 `cancel_url`；真实部署会把 confirm_url 放进确认邮件。

### 1.5 确认订阅

通过邮件 / 短信中的链接点击，或在测试环境直接调用：

```
GET /c/<token>      # 或
GET /api/subscriptions/confirm?token=<token>
```

- 状态由 `pending` 变 `active`，开始按 `reminder_level` 推算提醒时刻。

### 1.6 退订

```
POST /api/subscriptions/cancel
Content-Type: application/json

{"token": "<cancel_token>"}
```

- cancel_token 在订阅创建时随 cancel_url 返回；
- 邮件中通常以"取消订阅"按钮形式提供；
- 退订后状态变 `cancelled`，7 天后邮箱 / 手机号字段会被自动清空（PII 清理）。

### 1.7 通过 token 查看我的订阅

无需登录（旧版入口，使用订阅创建时返回的 token）。

```
GET /api/subscriptions/me?token=<cancel_token>
```

返回该订阅关联的考试 / 状态 / 渠道等基本信息；用于邮件中"管理我的订阅"链接落地。

### 1.7.1 查看我的订阅（已登录）

```
GET /api/account/me/subscriptions
Authorization: Bearer <token>
```

返回当前账号关联的所有订阅（按邮箱匹配）。

### 1.8 修改联系方式

```
PATCH /api/account/me
Authorization: Bearer <token>
Content-Type: application/json

{"phone": "13900139000"}                               # 改手机号
{"old_password": "old", "new_password": "new12345"}    # 改密码（旧密码必填）
```

- 手机号格式需合法（11-20 位）；
- 改密码后所有旧 token 立即失效。

### 1.9 邮箱迁移（换邮箱）

用于把当前账号的邮箱换成另一个邮箱（不影响订阅关系）。

```
POST /api/account/change-email
Authorization: Bearer <token>
Content-Type: application/json

{"new_email": "new@example.com", "current_password": "your-password"}
```

- 需要重新校验当前密码；
- 开发环境响应里直接返回 `dev_token`，方便测试；
- 生产环境 token 只通过**旧邮箱**的邮件链接发放。

```
GET /api/account/change-email/verify?token=<token>
```

- 校验通过后：账号 email 更新为新值、该账号关联的所有订阅 email 也同步迁移；
- 新邮箱立即生效，下次提醒发往新邮箱。

### 1.10 忘记密码 / 重置

```
POST /api/account/forgot-password
Content-Type: application/json

{"email": "you@example.com"}
```

- 若邮箱存在：通过邮件发送 30 分钟有效的重置链接；
- 若邮箱不存在：静默返回 200（不暴露账号是否存在）。

```
POST /api/account/reset-password
Content-Type: application/json

{"token": "<reset_token>", "new_password": "new-password"}
```

- 校验 token + 新密码长度；成功后立即更新密码并使 token 失效；
- 重置后旧 token 全部失效，需重新登录。

---

## 2. 管理员手册

### 2.1 管理员登录

```
POST /api/manage/login
Content-Type: application/json

{"username": "admin", "password": "<管理员密码>"}
```

- 用户名默认 `admin`；密码以 bcrypt 哈希存于环境变量 `MANAGE_PASSWORD_HASH`；
- 返回的 admin token 通过 `Authorization: Bearer <admin_token>` 传递；
- 首次部署时通过 `python -c "import bcrypt; print(bcrypt.hashpw(b'new-pwd', bcrypt.gensalt()).decode())"` 生成哈希。

### 2.2 考试目录管理

#### 2.2.1 新增考试

```
POST /api/manage/exams
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "name": "一级建造师 2026",
  "category": "工程",
  "organizer": "住建部 / 人社部",
  "registration_start": "2026-05-01T00:00:00+08:00",
  "registration_end":   "2026-05-30T00:00:00+08:00",
  "payment_end":        "2026-06-05T00:00:00+08:00",
  "admission_ticket_start": "2026-09-01T00:00:00+08:00",
  "exam_date":          "2026-09-15T09:00:00+08:00",
  "official_url": "https://www.mohurd.gov.cn/",
  "source_url":  "https://www.cpta.com.cn/2026-jz1",
  "source_hash": "...sha256(...",
  "status": "open"
}
```

- `source_url` 必填：原始公告链接，作为可追溯凭证；
- `source_hash`：对原文计算 SHA-256 后存，验证复用；
- `status` ∈ `draft` / `open` / `closed`：草稿不展示、已开放才推送给订阅者。

#### 2.2.2 列出考试

```
GET /api/manage/exams?status=open&category=IT
Authorization: Bearer <admin_token>
```

#### 2.2.3 调整考试状态

```
PATCH /api/manage/exams/{exam_id}/status
Authorization: Bearer <admin_token>
Content-Type: application/json

{"status": "draft"}
```

#### 2.2.4 复核考试数据

```
POST /api/manage/exams/{exam_id}/verify
Authorization: Bearer <admin_token>
```

- 把 `last_verified_at` 更新为当前时间、`verifier` 设为当前管理员；
- 复核后 30 天内会告警、90 天后自动 `draft` 化（数据可靠性约束）。

### 2.3 订阅查询

```
GET /api/manage/subscriptions?status=active&exam_id=12
Authorization: Bearer <admin_token>
```

返回所有订阅的列表（不含 token）。

### 2.4 通知日志

```
GET /api/manage/notifications?status=failed&limit=100
Authorization: Bearer <admin_token>
```

- 每条日志表示一次「订阅 × 节点 × 通道」的实际发送尝试；
- `status` ∈ `queued` / `sent` / `failed`：诊断失败原因时筛这一项；
- 同一 (订阅, 节点, 通道) 仅首次写日志，幂等由 DB 唯一约束保证。

### 2.5 数据看板

```
GET /api/manage/dashboard/overview
GET /api/manage/dashboard/exam-heatmap
GET /api/manage/dashboard/notification-success-rate
GET /api/manage/dashboard/stale-exams
```

均需 `Authorization: Bearer <admin_token>`。

- **overview**：考试 / 订阅 / 通知总数的总览；
- **exam-heatmap**：按类别统计订阅热度；
- **notification-success-rate**：各通道发送成功率（最近 30 天）；
- **stale-exams**：超过 30 天未复核的考试清单。

### 2.6 模板编辑器

```
GET    /api/manage/templates                       # 列出所有模板
GET    /api/manage/templates/{name}                # 读取单个
PUT    /api/manage/templates/{name}                # 覆盖保存（DB 优先于硬编码默认）
DELETE /api/manage/templates/{name}                # 删除（回退到硬编码默认）
```

PUT 请求体：

```json
{
  "subject": "【{exam_name}】{node_label}",
  "body": "考试：{name}\n类别：{category}\n主办：{organizer}\n...",
  "channel": "email"
}
```

- 修改后立即生效（无需发版）；
- `body` 必须包含占位符 `{cancel_url}`（或 SMS 短链），合规要求让用户随时可退订；
- 若误改可通过 DELETE 回退到内置默认模板。

### 2.7 健康检查

```
GET /api/manage/health
Authorization: Bearer <admin_token>
```

返回 DB / 调度器 / 通道注册表的内部状态，用于运维排障。

---

## 3. 公共约定

### 3.1 响应信封

所有 API 响应统一使用信封格式：

```json
{
  "ok": true,
  "data": { ... 业务字段 ... }
}
```

失败时：

```json
{
  "ok": false,
  "error": {
    "code": "invalid_email",
    "message": "邮箱格式不正确"
  }
}
```

错误码：`invalid_email` / `bad_credentials` / `email_taken` / `same_email` /
`invalid_token` / `unauthorized` / `not_found` / `internal_error` /
`rate_limited` 等。客户端应根据 `code` 字段做用户提示。

### 3.2 健康检查端点

- `GET /healthz`：进程存活探针，永远 200；
- `GET /readyz`：就绪探针，DB / 调度器 / 通道注册表全部就绪才 200。

### 3.3 时间字段

- 所有 datetime 字段均为 ISO-8601 + 时区（`+08:00` 上海时间）；
- 数据库存 UTC，应用层统一以 `Asia/Shanghai` 展示（见 `app/infra/time.py`）。

### 3.4 速率限制（生产部署）

反向代理（Nginx / 云 LB）建议：

| 端点 | 阈值 | 备注 |
| --- | --- | --- |
| `POST /api/account/*` | 10/min/IP | 防爆破 |
| `POST /api/subscriptions` | 30/min/IP | 防滥用 |
| `POST /api/manage/*` | 60/min/IP | 管理员侧 |

应用本身未内置限流；如需应用层限流建议前置 Envoy / APISIX。

### 3.5 错误响应示例

| HTTP | code | 场景 |
| --- | --- | --- |
| 400 | `invalid_email` | 邮箱格式不合法 |
| 400 | `same_email` | change-email 新旧邮箱相同 |
| 400 | `invalid_token` | confirm / cancel / reset token 错误或过期 |
| 400 | `bad_credentials` | 登录密码错 / 改密码旧密码错 |
| 401 | `unauthorized` | Bearer token 缺失或失效 |
| 404 | `not_found` / `exam_not_found` | 资源不存在 |
| 409 | `email_taken` | 注册 / change-email 时新邮箱已被占用 |
| 500 | `internal_error` | 未捕获异常（应通过日志排查） |

---

## 4. 常见问题

**Q: 注册时一直返回 `email_taken` 但我没注册过？**
A: 大概率是早期 demo 数据（`scripts/seed_demo.py`）灌入过；可联系管理员清空或换邮箱。

**Q: 订阅后没收到提醒？**
A: 检查 (1) 邮箱是否确认（`status` 应为 `active`）；(2) 考试 `status` 是否 `open`；(3) 管理员后台「通知日志」看是否有 `sent` 记录；(4) 检查垃圾邮件夹。

**Q: 改密码后其他设备立即失效吗？**
A: 是。改密码会立即让所有旧会话 token 失效（所有设备需重新登录）。

**Q: 邮箱迁移是否影响订阅？**
A: 不影响订阅关系；该账号关联的所有订阅 email 字段会同步迁移，下一次提醒直接发新邮箱。

**Q: 管理员忘记密码怎么办？**
A: 没有自助找回。需到部署机器上重新生成 `MANAGE_PASSWORD_HASH` 环境变量后重启服务；这是有意的安全设计。

---

## 5. 部署运维

> 面向部署 / 运维人员；用户手册到此为止时是阅读 §1-§4；以下内容是部署侧的延伸。

### 5.1 环境变量

| 变量 | 必填 | 含义 |
| --- | --- | --- |
| `APP_ENV` | 否 | `dev` / `test` / `prod`；影响日志级别与 dev_token 是否返回 |
| `DATABASE_URL` | 是 | SQLite：`sqlite:///./data.db`；PG：`postgresql+psycopg://user:pwd@host/db` |
| `HMAC_SECRET` | 是 | 订阅 / 退订 token 签名密钥；变更后所有旧 token 失效 |
| `LINK_SECRET` | 是 | ≥ 32 字节随机串；用于管理会话 token |
| `MANAGE_PASSWORD_HASH` | 是 | bcrypt 哈希；通过 `python -c "import bcrypt; print(bcrypt.hashpw(b'pwd', bcrypt.gensalt()).decode())"` 生成 |
| `ALIYUN_REGION` | 阿里云通道时 | cn-hangzhou / cn-shanghai 等 |
| `ALIYUN_ACCESS_KEY_ID` | 阿里云通道时 | 阿里云 AccessKey ID |
| `ALIYUN_ACCESS_KEY_SECRET` | 阿里云通道时 | 阿里云 AccessKey Secret |
| `ALIYUN_DM_ACCOUNT_NAME` | 邮件时 | 发件地址 `no-reply@example.com` |
| `ALIYUN_DM_FROM_ALIAS` | 邮件时 | 发件人别名 |
| `ALIYUN_SMS_SIGN_NAME` | 短信时 | 控制台审核通过的签名 |
| `ALIYUN_SMS_TEMPLATE_CODE` | 短信时 | 控制台审核通过的模板 code |
| `REDIS_URL` | 多实例时 | `redis://host:6379/0`；启用 RedisLock |
| `LOG_LEVEL` | 否 | DEBUG / INFO / WARNING / ERROR（默认 INFO） |

### 5.2 Docker 部署

```bash
# 拉取最新镜像
docker pull ghcr.io/growdu/kaoshile:latest

# 或指定版本
docker pull ghcr.io/growdu/kaoshile:v0.7.0

# docker-compose 启动（同时跑 web + 可选 worker）
DATABASE_URL=postgresql+psycopg://k:k@db/k \
HMAC_SECRET=$(openssl rand -hex 32) \
LINK_SECRET=$(openssl rand -hex 32) \
MANAGE_PASSWORD_HASH=$(python -c "import bcrypt; print(bcrypt.hashpw(b'adminpass', bcrypt.gensalt()).decode())") \
docker compose up -d
```

### 5.3 初始化与数据导入

```bash
# 首次部署：迁移 + 灌入 demo 数据
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed_demo.py    # 幂等，可重复执行

# 健康检查
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

### 5.4 反向代理（Nginx 示例）

```nginx
server {
    listen 443 ssl http2;
    server_name kaoshile.example.com;
    ssl_certificate     /etc/ssl/certs/kaoshile.pem;
    ssl_certificate_key /etc/ssl/private/kaoshile.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size 1m;

        # 速率限制（与 §3.4 一致）
        limit_req zone=account burst=20 nodelay;
    }
}
```

### 5.5 日志与可观测

- 应用日志：stdout；生产侧建议接 Loki / ELK / 云日志服务；
- 结构化字段：`event` / `level` / `subscription_id` / `channel` / `node` / `attempt`；
- 敏感字段（access_key / secret / phone / email / password / token / link_secret）在日志中**自动脱敏**（见 `app/infra/logging.py`）；
- 健康检查 / 存活 / 就绪三件套已在 §3.2 说明。

---

## 6. 故障排查

### 6.1 订阅提交后未收到确认邮件

按以下顺序排查：

1. `/api/manage/notifications?status=failed` 是否有该订阅的失败记录？
   - 有：点开看 `error_message`；常见为阿里云 DM 模板未审核通过 → 在控制台报备后重发；
   - 无：继续 2。
2. `/api/manage/subscriptions?email=...` 看订阅 `status`：
   - `pending`：用户没点确认链接 → 重发确认邮件；
   - `active`：订阅正常，问题在通知扇出阶段 → 继续 3。
3. `scan_now()` 是不是被锁运行过？`grep scan_skipped_lock_hed` 看是否多实例抢锁失败。
4. 阿里云 DM / SMS 服务侧：登录控制台查看发送记录（按回执 ID）。

### 6.2 节点到了但没触发通知

| 现象 | 可能原因 |
| --- | --- |
| 监控显示 scheduler 没启动 | `app/main.py` 中 scheduler 启动失败；看启动日志 `scheduler_started` / `scheduler_failed` |
| 调度器启动但 `scan_skipped_lock_hed` | 多实例抢锁失败（默认仅一个能跑） |
| `scan_now` 跑但日志显示无 active 订阅 | 订阅被批量退订 / 数据库连接断开 |
| `dispatch` 返回 false 但日志无 error | 幂等命中（已发过）；属正常行为 |

### 6.3 邮箱迁移失败

| 错误码 | 含义 | 解决 |
| --- | --- | --- |
| `invalid_email` | 新邮箱格式不合法 |
| `email_taken` | 新邮箱已被另一账号占用 | 让用户换邮箱 |
| `bad_credentials` | 当前密码错 |
| `invalid_token` | 验证链接过期或已被消费 | 重新发起 change-email |
| `user_not_found` | token 对应的用户不存在 | 重新发起 |

### 6.4 数据库锁 / 连接池耗尽

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 is reached
```

→ 调大 SQLAlchemy pool_size；或检是否有未关闭的会话（最常见：usecase 异常路径未 `session.close()`）。

### 6.5 重置管理员密码

```bash
# 在部署机器上：
NEW=$(python -c \"import bcrypt; print(bcrypt.hashpw(b'new-password', bcrypt.gensalt()).decode())\")
# 写到环境变量后重启：
docker compose up -d --force-recreate api
```

---

## 7. 升级流程

### 7.1 小版本升级（v0.6.x → v0.7.x）

1. 拉新镜像：`docker compose pull api`；
2. 跑迁移：`docker compose exec api alembic upgrade head`（如有新迁移）；
3. 重启：`docker compose up -d --force-recreate api`；
4. 验证：`/healthz` + `/readyz` + `scripts/smoke.py`（in-process 测试）。

### 7.2 大版本升级（含破坏性变更）

1. 在 staging 环境先升级 + 验证全链路；
2. 备份数据库：`pg_dump` 或 `sqlite3 .backup`；
3. 阅读新版本 `CHANGELOG.md` 中的「变更 / 移除」段落；
4. 若需新环境变量，先在 `.env` 加好；
5. 跑 `alembic upgrade head`；
6. 滚动重启：先启新实例验证 `readyz`，再切流量；
7. 观察 30 分钟：发送成功率应 ≥ 历史 P95。

### 7.3 回滚

```bash
# 1. 切回上一个镜像
docker compose pull api:previous-tag
docker compose up -d --force-recreate api

# 2. 必要时回退迁移
docker compose exec api alembic downgrade -1
```

> 回退迁移**仅在确认无新数据依赖新 schema 时**才安全；带数据迁移的版本升级通常不能简单回滚，需提前备份。

### 7.4 备份建议

| 数据 | 方式 | 频率 |
| --- | --- | --- |
| SQLite | `sqlite3 db.sqlite3 ".backup backup.db"` | 每日 |
| PostgreSQL | `pg_dump` + WAL 归档 | 每日 + 持续归档 |
| `MANAGE_PASSWORD_HASH` 之外的 `.env` | 加密存储在密码管理器 | 变更即备份 |

> 备份**不要**包含 `.env`（含密钥 / 密码），存密码管理器即可。