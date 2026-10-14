# 考试通知软件 — 文档索引

> 项目代号：**kaoshile**（考试乐）
> 文档版本：v7.0（2026-10-14）
> 维护者：Mavis

本目录存放考试通知软件的**需求、设计与实现方案**。所有开发活动以本文档集合为准；任何需求或架构变更需先更新文档，再动手改代码。

---

## 文档清单

| 文件 | 用途 | 受众 |
| --- | --- | --- |
| [README.md](./README.md) | 文档索引与关键决策记录（本文） | 所有人 |
| [requirements.md](./requirements.md) | 需求文档：业务目标、功能性 / 非功能性需求、验收标准 | 产品 / 研发 / 测试 |
| [design.md](./design.md) | 设计文档：架构、技术栈、模块、数据模型、关键流程、API | 研发 |
| [implementation.md](./implementation.md) | 实现方案：里程碑、目录结构、代码骨架、测试策略、commit 节奏 | 研发 |
| [data_sources.md](./data_sources.md) | 数据源策略与白名单：数据从哪儿来、怎么录、怎么复核 | 研发 / 数据维护员 |
| [seed_exams.md](./seed_exams.md) | 首屏考试目录初始灌入清单（10 类 50+ 场考试） | 研发 / 数据维护员 |
| [user_manual.md](./user_manual.md) | 用户手册：API 用法、错误码、FAQ；覆盖普通用户 + 管理员路径 + 部署运维 + 故障排查 + 升级流程 | 后期维护 / 二开 / 客户对接 / 运维 |
| [best_practices.md](./best_practices.md) | 最佳实践：commit 节奏、测试策略、文档维护、安全、性能、部署、反模式 | 研发 / 运维 |
| [../CHANGELOG.md](../CHANGELOG.md) | 版本更新日志（Keep a Changelog + SemVer） | 所有人 |

建议阅读顺序：**README → requirements → data_sources / seed_exams → design → implementation → best_practices（工程时翻阅）→ user_manual（运维 / 接入时翻阅）→ CHANGELOG（看变更时翻阅）**。

---

## 一句话项目说明

用户在前端选择目标考试并填写邮箱 / 手机号，后台根据考试的关键时间点（报名开始、报名截止、缴费截止、准考证打印、考试日），在合适时间通过**阿里云邮件推送 + 阿里云短信**向用户发送提醒。

---

## 关键决策记录（DoR / Definition of Ready）

| 项 | 决策 | 备注 |
| --- | --- | --- |
| 软件形态 | Web 应用（前后端分离） | 用户可浏览器访问 |
| 技术栈 | Python 3.11 + FastAPI + APScheduler | 见 `design.md §2.1` 推荐理由 |
| 邮件通道 | 阿里云邮件推送（DirectMail） | 国内送达率高，中文文档完善 |
| 短信通道 | 阿里云短信（SMS） | 与邮件同账号管理 |
| 数据存储 | SQLite（开发期）/ PostgreSQL（生产） | 见 `design.md` 数据层 |
| 调度机制 | APScheduler AsyncIOScheduler + 内存队列 | 见 `design.md` 调度层 |
| 部署目标 | 单进程 Docker 容器起步，可横向扩展为 Worker 拆分 | 见 `design.md` 部署拓扑 |
| 数据来源 | v1 人工录入 + 解析助手；v1.1 RSS 聚合；v2 受限抓取 | 见 `data_sources.md` |
| 首屏考试 | 按 `seed_exams.md` 录入，初始 10 类 50+ 场 | 见 `seed_exams.md` |
| 复核机制 | 30 天未复核告警、90 天未复核自动 `draft` 化 | 见 `data_sources.md §4.4` |

任何后续决策的变更都需要：
1. 在本文档「关键决策记录」追加一行；
2. 同步更新 `design.md` 或 `implementation.md` 对应章节；
3. 在 commit message 中引用文档版本号。

---

## 后续开发建议

按 `implementation.md` 中的里程碑推进，每个子模块完成后立即 commit，并配套单元测试 + 集成测试。详情见 `implementation.md` 的「开发节奏」一节。

---

## 更新日志

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-10-13 | 初始版本：建立 README、requirements、design、implementation |
| v0.2 | 2026-10-13 | 新增 `data_sources.md` / `seed_exams.md`；更新 requirements / README 引用数据源策略 |
| v1.0 | 2026-10-13 | v1 上线就绪：implementation.md 全部 14 个里程碑 ✅；248 测试全绿；文档更新到 v1.0 |
| v2.0 | 2026-10-13 | v2 完成：解析助手 / 受限抓取器 / 数据看板 / 微信通道；283 测试全绿 |
| v3.0 | 2026-10-14 | v3 完成：钉钉/飞书通道 / 多实例 Redis 锁 / 用户账号体系 / 模板编辑器；332 测试全绿 |
| v4.0 | 2026-10-14 | v4 完成：用户自助修改联系方式 / 批量通知队列；341 测试全绿 |
| v5.0 | 2026-10-14 | v5 完成：邮箱迁移（双确认流程）+ 端到端冒烟脚本；351 测试全绿 |
| v6.0 | 2026-10-14 | v6 完成：用户手册 + GitHub Actions CI（lint/test/smoke/docker）+ 完整度自动校验；360 测试全绿 |
| v7.0 | 2026-10-14 | v7 完成：Release workflow + Dependabot + CODEOWNERS + Issue/PR 模板 + CHANGELOG；需求 / 设计 / 用户手册补强；新建 best_practices.md；369 测试全绿 |
