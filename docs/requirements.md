# 需求文档 — 考试通知软件

> 版本：**v7.0**（2026-10-14）
> 对应实现版本：v0.1（v1）→ v0.7（v7.0）
> 维护者：Mavis

本文档描述业务目标、功能性 / 非功能性需求、数据需求、验收标准；实现细节与里程碑拆分见 [`implementation.md`](./implementation.md)，架构 / 技术栈 / API 详见 [`design.md`](./design.md)，面向用户的接口用法见 [`user_manual.md`](./user_manual.md)，开发 / 运维最佳实践见 [`best_practices.md`](./best_practices.md)。

---

## 1. 项目背景

### 1.1 现状与痛点

- 各类资格考试（建造师、会计师、教师资格、研究生、软考、医疗、公务员等）报名时间分散且周期短，错过报名 / 缴费 / 打印准考证窗口的比例极高；
- 官方公告多发布在不易持续关注的网页上，普通用户难以聚合；
- 即便记住了日期，临到头仍可能因忙碌忘记；
- 短信 / 邮件提醒是低成本且覆盖率最高的渠道，但目前缺少一个**轻量、开箱即用、用户自助选择考试并订阅提醒**的产品。

### 1.2 项目目标

做一个**用户自助订阅考试提醒**的轻量 Web 服务：

1. 提供一份**考试目录**，包含每场考试的关键时间节点（报名开始 / 报名截止 / 缴费截止 / 准考证打印 / 考试日）；
2. 用户在前端选择要订阅的考试，留下邮箱 + 手机号；
3. 后台在每个关键节点的**指定提前量**（如考前 7 天 / 3 天 / 当天）自动发送邮件和短信提醒；
4. 用户可随时查询订阅状态、退订、修改联系方式、迁移邮箱；
5. 提供管理后台录入与维护考试数据，含数据看板和模板编辑能力。

### 1.3 已实现的能力（v1 → v7）

| 版本 | 已交付能力 |
| --- | --- |
| v1 | 考试目录 CRUD、订阅 / 确认 / 退订、APScheduler + node_scanner + 阿里云通道、Docker、seed_demo、复核 watchdog、PII 清理 |
| v2 | 解析助手 parse_helper、受限抓取器 Fetcher、数据看板 API、微信通道 |
| v3 | 钉钉 / 飞书通道、Redis 分布式锁、用户账号体系、模板编辑器 |
| v4 | 用户自助修改联系方式、批量通知队列 |
| v5 | 邮箱迁移（双确认）、端到端冒烟脚本 |
| v6 | 用户手册、GitHub Actions CI（lint + test + smoke + docker） |
| v7 | Release workflow + Dependabot + CODEOWNERS + Issue/PR 模板、CHANGELOG、本文档集升级 |

### 1.4 非目标（任何版本都不做）

- 报名 / 缴费 / 准考证打印的**实际代办**（本服务只做提醒，不代操作）；
- 主动爬取公告原文（v1-v7 不抓任何页面；白名单抓取由受限 Fetcher 在管理员批准后接入，仍不入自动入库路径）；
- 商业 / 厂商认证（PMP、阿里云 / 华为云 / 腾讯云 / AWS、CISCO、Red Hat、ACCA/CFA/FRM 等）——它们有自己的平台，节奏完全不同；
- 多语言（当前仅简体中文）；
- 移动端原生 App（响应式 Web 即可）；
- 付费 / 会员体系。

> 数据来源策略详见 [`data_sources.md`](./data_sources.md)，首屏灌入清单见 [`seed_exams.md`](./seed_exams.md)。

---

## 2. 用户角色

| 角色 | 描述 | 主要诉求 |
| --- | --- | --- |
| **访客** | 未订阅的用户 | 浏览考试目录、了解时间节点 |
| **订阅用户** | 已留下联系方式的用户（含注册用户） | 接收考试提醒、查看 / 修改自己的订阅、退订、迁移邮箱 |
| **管理员** | 维护考试目录与系统配置的角色 | 录入 / 修改考试、查看发送日志、处理异常、看看板、改模板 |

---

## 3. 业务流程（核心场景）

### 3.1 主流程：订阅考试

```
[访客]
  ↓ 打开首页 / 考试目录
  ↓ 选择某场考试
  ↓ 进入「订阅」页
  ↓ 填写邮箱 + 手机号 + 期望的提醒提前量
  ↓ 点击「订阅」
[系统]
  ↓ 入库订阅记录（status=pending）
  ↓ 发送「确认邮件 / 短信」（含确认链接）
  ↓ 等待用户点击确认
  ↓ 点击确认链接 → status=active
  ↓ 按时间调度，发送通知
[订阅用户]
  │   在节点前 7d / 3d / 1d / 当天收到邮件 + 短信
  │   可随时点邮件里的「退订」或访问「我的订阅」页
  ↓ 也可通过注册账号 → 登录后查看 / 改联系方式 / 迁移邮箱
```

### 3.2 通知触发节点（每场考试共 5 类）

| 节点 | 默认提前量（standard） | 备注 |
| --- | --- | --- |
| 报名开始 | 开始时刻前 1 天 | 提醒：今日可报名 |
| 报名截止 | 截止前 3 天、1 天、当天 9:00 | 三次提醒 |
| 缴费截止 | 截止前 3 天、1 天、当天 9:00 | 三次提醒 |
| 准考证打印开始 | 开始前 1 天 | 提醒：明日起可打印 |
| 考试日 | 考前 7 天、3 天、1 天、当天 7:00 | 四次提醒 |

> 提前量可由订阅用户在订阅时按考试维度选择预设档位（保守 / 标准 / 强烈），详见 §5.3。

### 3.3 退订流程

- 邮件 / 短信内含**退订链接**（带 token），点击即可将订阅标记为 `cancelled`，不再发送任何通知；
- 退订为软删除（保留记录），便于管理员审计；
- 退订后 7 天内彻底清空 PII（邮箱、手机号），保留订阅主记录用于审计（id、节点哈希、状态）。

### 3.4 邮箱迁移流程（v5 新增）

```
用户已登录
  ↓ POST /api/account/change-email {new_email, current_password}
[系统] 校验旧密码 + 邮箱格式 → 签发确认 token
  ↓ 通过旧邮箱发送验证链接（含 token）
用户点击链接
  ↓ GET /api/account/change-email/verify?token=...
[系统] 校验 token → 更新 user.email + 该用户所有订阅 email 字段
```

---

## 4. 功能性需求

按优先级排序：**P0 = 必须**；**P1 = 应有**；**P2 = 期望**。

### 4.1 考试目录 [P0]

- **F1.1** 首页展示所有**可订阅**的考试（status=open 且未到报名截止）；
- **F1.2** 考试详情页：展示名称、主办方、报名窗口、缴费窗口、准考证打印窗口、考试日、官方公告链接；
- **F1.3** 支持按「关键字 / 类别 / 时间区间」过滤；
- **F1.4** 状态字段：草稿（draft）、开放订阅（open）、报名截止（registration_closed）、归档（archived）。

### 4.2 订阅管理 [P0]

- **F2.1** 在考试详情页点击「订阅」，进入订阅表单；
- **F2.2** 订阅表单字段：
  - 邮箱（必填，校验格式）
  - 手机号（必填，校验中国大陆 11 位）
  - 提醒档位（单选：保守 / 标准 / 强烈，默认标准）
  - 通知通道勾选（默认邮件 + 短信全开，可单选 email / sms / wechat / dingtalk / feishu）
- **F2.3** 提交后立即发送**确认邮件 + 确认短信**（双通道确认，避免无效订阅）；
- **F2.4** 用户点击确认链接 → `status=active`；
- **F2.5** 「我的订阅」页（通过邮箱 + token 访问，或登录后访问）展示所有 active / pending 订阅，可修改联系方式 / 退订。

### 4.3 用户账号体系 [P1, v3+]

- **F3.1** 用户可注册账号（邮箱 + 密码），无需实名；
- **F3.2** 登录后 1 天有效期的会话 token；
- **F3.3** 忘记密码：邮件发送 30 分钟有效重置链接；
- **F3.4** 修改联系方式（手机号 / 密码）；
- **F3.5** 邮箱迁移（双确认流程，见 §3.4）。

### 4.4 提醒档位 [P1]

| 档位 | 报名截止 | 缴费截止 | 准考证 | 考试日 |
| --- | --- | --- | --- | --- |
| 保守 | 前 1 天 | 前 1 天 | 前 1 天 | 前 3 天、当天 |
| 标准（默认） | 前 3 天、1 天、当天 | 前 3 天、1 天、当天 | 前 1 天 | 前 7 天、3 天、1 天、当天 |
| 强烈 | 前 7 天、3 天、1 天、当天 | 前 7 天、3 天、1 天、当天 | 前 3 天、1 天 | 前 14 天、7 天、3 天、1 天、当天 |

### 4.5 通知发送 [P0]

- **F5.1** 后台调度器在每场考试每个节点的**发送时刻**触发；
- **F5.2** 通过所选通道并行发送：阿里云邮件 / 阿里云短信 / 微信（corp）/ 钉钉 / 飞书；
- **F5.3** 模板渲染：节点类型 + 考试名 + 时间 + 用户称呼 + 退订链接；
- **F5.4** 发送结果入库（成功 / 失败 / 失败原因 / 第三方回执 ID）；
- **F5.5** 失败重试：单条通知失败后，指数退避重试（1s / 5s / 25s）；最终失败标记 `failed`；
- **F5.6** 发送频率限制：同一 (订阅, 节点, 通道) 仅首次写 NotificationLog（idempotent，DB 唯一约束保证）；
- **F5.7** 批量通知队列（v4）：高峰期通过 asyncio Queue + worker 扇出，重试避免 join 死锁。

### 4.6 通知历史 [P1]

- 用户「我的订阅」页可看到**已发送**的通知列表（时间、通道、状态）；
- 管理员后台可见全部发送日志，支持按考试 / 时间 / 状态 / 通道筛选。

### 4.7 管理员后台 [P0]

- **F7.1** 登录入口（账号 + 密码，bcrypt 校验）；
- **F7.2** 考试 CRUD：录入字段见 §7.1；
- **F7.3** 订阅列表查询（按考试 / 状态）；
- **F7.4** 发送日志查询；
- **F7.5** 模板编辑（DB 优先 + 默认 fallback，无需发版即可改文案）；
- **F7.6** 数据看板（总览 / 类别热度 / 通道成功率 / 过期考试清单）。

### 4.8 退订与合规 [P0]

- **F8.1** 所有通知正文末尾必须包含**退订链接**；
- **F8.2** 用户点退订链接后立即生效，无需登录；
- **F8.3** 退订后 7 天内彻底删除 PII（邮箱、手机号），保留订阅主记录用于审计（id、节点哈希、状态）。

### 4.9 数据可靠性 [P0]

- **F9.1** 每条考试必填 `source_url`（原始公告链接）；
- **F9.2** 复核机制：`last_verified_at` 超过 30 天在管理后台告警，超过 90 天自动 `draft` 化；
- **F9.3** 数据源白名单：解析助手 + 受限 Fetcher 仅对 `data_sources.md` 列出的权威源生效；
- **F9.4** `source_hash`（SHA-256 of 公告正文）：用于变更检测。

---

## 5. 非功能性需求

### 5.1 可用性

- **NFR-U1** 服务可用率目标 ≥ 99%（按月计算）；
- **NFR-U2** 单实例故障恢复时间 ≤ 5 分钟；
- **NFR-U3** 健康检查：`/healthz`（存活）+ `/readyz`（就绪：DB / 调度器 / 通道注册表全部 OK）。

### 5.2 性能

- **NFR-P1** 订阅提交到确认邮件发送的端到端延迟 ≤ 5 秒（P95）；
- **NFR-P2** 单实例调度器每秒可处理 ≥ 50 条通知触发的扇出；
- **NFR-P3** 考试目录页首屏加载 ≤ 2 秒（P95，4G 网络）；
- **NFR-P4** 端到端冒烟脚本 `scripts/smoke.py` 8 步跑通时间 ≤ 5 秒（in-process）。

### 5.3 安全

- **NFR-S1** 邮箱 / 手机号在数据库中**不加密**（业务需要按邮箱查询），但**传输层 TLS**，且管理员查询需登录；
- **NFR-S2** 退订 / 订阅 / 重置 / 邮箱迁移 token 使用 HMAC-SHA256 签名；
- **NFR-S3** 所有管理后台接口强制鉴权；
- **NFR-S4** 阿里云 AccessKey 通过**环境变量**注入，禁止入库；日志 / 通知中**禁止出现**敏感字段（access_key / secret / phone / email / password / token / link_secret）；
- **NFR-S5** bcrypt cost ≥ 12 存用户密码；改密码后旧 token 全部失效；
- **NFR-S6** 管理员密码重置**没有自助路径**，需运维介入（有意设计，避免被爆破）。

### 5.4 可观测

- **NFR-O1** 所有外部调用（邮件 / 短信 API）记录结构化日志（时间、订阅 ID、通道、结果、回执 ID）；
- **NFR-O2** 关键操作（订阅 / 退订 / 发送失败 / 邮箱迁移）落审计日志；
- **NFR-O3** 结构化日志（structlog）+ 敏感字段自动脱敏。

### 5.5 可扩展性

- **NFR-E1** 通知通道抽象为 Protocol，新增通道不改动业务代码；
- **NFR-E2** 调度器与 Web 服务同进程起步，但代码上解耦，可拆为独立 Worker；
- **NFR-E3** 多实例部署：通过 Redis 锁（v3+ 默认 `redis_lock` extra 启用）保证节点扇出不重复；
- **NFR-E4** 模板渲染：DB 优先 + 硬编码 fallback，无需发版即可调整文案。

### 5.6 可测试性

- **NFR-T1** 任何业务模块必须有对应单元测试（happy + 至少 1 个失败路径）；
- **NFR-T2** 关键流程（订阅 / 通知发送 / 退订 / 邮箱迁移）必须有集成测试覆盖；
- **NFR-T3** 外部通道（邮件 / 短信 / 微信 / 钉钉 / 飞书）在测试中必须可被 Mock 替换；
- **NFR-T4** 测试隔离：`tests/conftest.py` autouse fixture 重置 engine / registry / scheduler / structlog；
- **NFR-T5** 端到端冒烟脚本 `scripts/smoke.py` 必须在 CI 中跑通。

### 5.7 可维护性

- **NFR-M1** 单文件不超过 ~300 行（超过即拆）；
- **NFR-M2** 函数不超过 ~50 行，缩进 ≤ 3 层；
- **NFR-M3** 文档与代码同步：每次新增 / 修改 API 必须同步更新 `user_manual.md`（由 `tests/unit/test_user_manual.py` 自动校验）；
- **NFR-M4** 文档完整：requirements / implementation / design / user_manual / best_practices / README / CHANGELOG 七件套；
- **NFR-M5** CI 必跑：`pytest` + `scripts/smoke.py` 必须在所有 push / PR 通过。

### 5.8 部署 / 运维

- **NFR-D1** Docker 镜像 + docker-compose 起步；可拆为 API worker + 通知 worker；
- **NFR-D2** 镜像同时推送 GHCR（见 `.github/workflows/release.yml`）；
- **NFR-D3** 时间统一使用 **Asia/Shanghai**（UTC+8）；
- **NFR-D4** 关键配置（HMAC_SECRET / LINK_SECRET / MANAGE_PASSWORD_HASH / 阿里云 AK）通过环境变量注入，**禁止入库**；
- **NFR-D5** Alembic 迁移：schema 演进与禁止手动改库。

### 5.9 国际化

- **NFR-I1** 当前仅简体中文；API 错误消息 / 文案均简体中文；
- **NFR-I2** 未来引入第二语言时不得破坏现有字段命名。

---

## 6. 业务流程（订阅 / 退订 / 通知）不变项

### 6.1 通知触发节点

见 §3.2。

### 6.2 通知通道优先级

订阅时默认勾选 `[email, sms]`；用户可去除其一或追加 `[wechat, dingtalk, feishu]`，但新增通道若未被管理员启用会被静默忽略（避免配置漂移）。

---

## 7. 数据需求

### 7.1 考试（Exam）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | int / uuid | 系统 | 主键 |
| name | string | 是 | 考试名 |
| category | string | 是 | 类别枚举：IT / 财经 / 医药 / 工程 / 教育 / 其他 |
| organizer | string | 否 | 主办方 |
| registration_start | datetime | 是 | 报名开始 |
| registration_end | datetime | 是 | 报名截止 |
| payment_end | datetime | 否 | 缴费截止 |
| admission_ticket_start | datetime | 否 | 准考证打印开始 |
| exam_date | datetime | 是 | 考试日 |
| official_url | string | 否 | 官方公告链接 |
| source_url | string | 是 | 录入时所依据的公告 URL（复核凭证） |
| source_hash | string | 否 | 公告正文 SHA256（变更检测） |
| last_verified_at | datetime | 否 | 上次人工复核时间，>30d 告警，>90d 自动 draft |
| verifier | string | 否 | 上次复核的管理员账号 |
| status | enum | 是 | draft / open / registration_closed / archived |
| created_at / updated_at | datetime | 系统 | |

### 7.2 订阅（Subscription）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 系统 | 主键 |
| exam_id | int | 是 | 外键 |
| user_id | uuid | 否 | 关联用户（已注册账号时） |
| email | string | 是 | 邮箱（小写） |
| phone | string | 是 | 手机号（11 位） |
| reminder_level | enum | 否 | conservative / standard / aggressive |
| channels | json | 否 | ["email","sms","wechat","dingtalk","feishu"] |
| status | enum | 是 | pending / active / cancelled |
| confirm_token | string | 系统 | HMAC 签名 |
| cancel_token | string | 系统 | HMAC 签名 |
| created_at / confirmed_at / cancelled_at | datetime | 系统 | |

### 7.3 用户（User, v3+）

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 系统 | 主键 |
| email | string | 是 | 唯一索引 |
| password_hash | string | 是 | bcrypt cost ≥ 12 |
| created_at / updated_at | datetime | 系统 | |
| last_login_at | datetime | 否 | |

### 7.4 通知发送记录（NotificationLog）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| subscription_id | uuid | 外键 |
| exam_id | int | 外键 |
| node_type | enum | registration_start / registration_end / payment_end / admission_start / exam_day |
| channel | enum | email / sms / wechat / dingtalk / feishu |
| status | enum | queued / sent / failed |
| attempt_count | int | 重试次数 |
| vendor_receipt_id | string | 第三方回执 |
| error_message | string | 失败原因 |
| sent_at | datetime | 实际发送时间 |

### 7.5 模板（Template, v3+）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| name | string | 主键：`{channel}__{node}` 形式 |
| channel | enum | email / sms |
| subject | string | 邮件主题（短信忽略） |
| body | string | 模板正文，必须含 `{cancel_url}` 占位符 |
| updated_at | datetime | 最后修改时间 |
| updated_by | string | 修改者（管理员账号） |

---

## 8. 约束与假设

- **C1** 阿里云账户已开通 DirectMail 与 SMS 服务，且完成签名 / 模板报备；
- **C2** 短信签名与模板必须事先在阿里云控制台审核通过（合规要求）；
- **C3** 多实例调度器需启用 Redis 锁（v3+ 默认 `redis_lock` extra）；
- **C4** 时间统一使用 **Asia/Shanghai**（UTC+8）；
- **C5** 考试目录数据由管理员手工维护，受限 Fetcher 仅对白名单源启用，仍需人工批准入库；
- **C6** 首屏考试目录的初始灌入清单按 [`seed_exams.md`](./seed_exams.md) 落地，灌入前管理员必须人工复核；
- **C7** 每条考试记录带 `last_verified_at` 字段，超过 30 天未复核时进入管理员后台告警；超过 90 天自动转入 `draft` 状态；
- **C8** 数据库开发期使用 SQLite，生产期使用 PostgreSQL；迁移通过 Alembic 完成，**禁止手动改库**；
- **C9** 不引入新的依赖必须经过 v6+ CI 验证（lint + test + smoke）。

---

## 9. 验收标准

满足以下全部条件视为每个版本完成：

### 9.1 通用

1. ✅ 全部 P0 / P1 功能项实现并通过测试；
2. ✅ 每个 commit 配套单元测试 + 集成测试，且 `pytest` 在本地全绿；
3. ✅ `scripts/smoke.py` 在本地跑通（CI 也跑）；
4. ✅ `docs/user_manual.md` 包含本次新增 / 修改的所有 API 路径（由 `tests/unit/test_user_manual.py` 自动校验）；
5. ✅ README / requirements / design / implementation / user_manual / best_practices / CHANGELOG 与代码一致；
6. ✅ 敏感字段（access_key / secret / phone / email / password / token / link_secret）不出现在日志 / 通知中；
7. ✅ Docker 构建成功（CI 守门）。

### 9.2 v7 专项

1. ✅ Release workflow 在打 `v*` tag 时自动构建镜像 + 推 GHCR + 创建 GitHub Release；
2. ✅ Dependabot 自动跟踪 pip / GitHub Actions 依赖；
3. ✅ CODEOWNERS 至少有一条默认 owner 规则；
4. ✅ CHANGELOG.md 含 `[Unreleased]` 与至少一个历史版本。

---

## 10. 后续迭代方向

按用户偏好「每个子模块完成立即 commit，且必须配套单元 + 集成测试」推进；任何新方向先在 §1.4 非目标中确认未越界，再追加版本。

- **v8**：分布式追踪（OpenTelemetry）+ Prometheus 指标；
- **v8**：通知送达回执采集（IMAP / 短信回执 Report）；
- **v9**：用户自助申报入口（详情 + 贡献者信誉系统雏形）；
- **v10**：响应式 Web 前端（与 FastAPI 同仓库或独立仓库）；
- **v11**：国际化（英文 / 繁中）；
- **v12**：Webhook 出站（用户可配置把通知镜像到自定义 HTTP 端点）。

---

> 文档结束。任何变更请同步更新版本号、日期与本文档末尾的更新日志。

| 版本 | 日期 | 变更摘要 |
| --- | --- | --- |
| v0.1 | 2026-10-13 | 初始版本（v1 MVP） |
| v7.0 | 2026-10-14 | 升级到 v7：新增 v2-v7 已实现能力清单（§1.3）；邮箱迁移流程（§3.4）；多通道 P2（§4.5）；CI / 文档 / 部署 / 国际化非功能性需求（§5）；数据需求新增 User / Template；验收标准细化为通用 + v7 专项（§9）；后续迭代方向（§10） |