# 考试通知软件 — 文档索引

> 项目代号：**kaoshile**（考试乐）
> 文档版本：v0.1（2026-10-13）
> 维护者：Mavis

本目录存放考试通知软件的**需求、设计与实现方案**。所有开发活动以本文档集合为准；任何需求或架构变更需先更新文档，再动手改代码。

---

## 文档清单

| 文件 | 用途 | 受众 |
| --- | --- | --- |
| [requirements.md](./requirements.md) | 需求文档：业务目标、功能性 / 非功能性需求、验收标准 | 产品 / 研发 / 测试 |
| [design.md](./design.md) | 设计文档：架构、技术栈、模块、数据模型、关键流程、API | 研发 |
| [implementation.md](./implementation.md) | 实现方案：里程碑、目录结构、代码骨架、测试策略、commit 节奏 | 研发 |

建议阅读顺序：**requirements → design → implementation**。

---

## 一句话项目说明

用户在前端选择目标考试并填写邮箱 / 手机号，后台根据考试的关键时间点（报名开始、报名截止、缴费截止、准考证打印、考试日），在合适时间通过**阿里云邮件推送 + 阿里云短信**向用户发送提醒。

---

## 关键决策记录（DoR / Definition of Ready）

| 项 | 决策 | 备注 |
| --- | --- | --- |
| 软件形态 | Web 应用（前后端分离） | 用户可浏览器访问 |
| 技术栈 | 待 `design.md` 推荐（Python FastAPI + APScheduler 为推荐项） | 由设计文档给出理由 |
| 邮件通道 | 阿里云邮件推送（DirectMail） | 国内送达率高，中文文档完善 |
| 短信通道 | 阿里云短信（SMS） | 与邮件同账号管理 |
| 数据存储 | SQLite（开发期）/ PostgreSQL（生产） | 见 `design.md` 数据层 |
| 调度机制 | APScheduler（内存 + 持久化作业存储） | 见 `design.md` 调度层 |
| 部署目标 | 单进程 Docker 容器起步，可横向扩展为 Worker 拆分 | 见 `design.md` 部署拓扑 |

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
