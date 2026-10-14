# 更新日志

本项目的用户可见变更记录在这里维护（按 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 约定）。

格式：版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)；每个版本下分「新增 / 变更 / 修复 / 移除 / 安全」五类（如对应章节为空可省）。

## [Unreleased]

待发布。

## [v0.6.0] - 2026-10-14

### 新增

- 用户手册 `docs/user_manual.md`：覆盖普通用户 + 管理员路径 + 公共约定 + FAQ。
- GitHub Actions CI：lint + test + smoke + docker build。
- 依赖自动追加：Dependabot 配置 + CODEOWNERS + Issue / PR 模板。

## [v0.5.0] - 2026-10-14

### 新增

- 邮箱迁移：双确认流程（旧密码 + 新邮箱验证链接）。
- 端到端冒烟脚本 `scripts/smoke.py`：8 步主链路 in-process 验证。

## [v0.4.0] - 2026-10-14

### 新增

- 用户自助修改联系方式（手机号 + 密码）。
- 批量通知队列（asyncio Queue + worker + 重试入队）。

## [v0.3.0] - 2026-10-14

### 新增

- 钉钉 / 飞书通知通道（webhook + 加签）。
- Redis 分布式锁（抽象 + 默认 InMemory + RedisLock 占位）。
- 用户账号体系（注册 / 登录 / 找回 / 重置）。
- 模板编辑器（DB 优先 + 默认 fallback）。

## [v0.2.0] - 2026-10-13

### 新增

- 解析助手 parse_helper（4 种日期格式 + 缺失字段提示）。
- 受限抓取器 Fetcher（白名单 + robots.txt 缓存 + 6h 冷却）。
- 数据看板 API（overview / heatmap / success-rate / stale-exams）。
- 微信通知通道（Mock + corp access_token 占位）。

## [v0.1.0] - 2026-10-13

### 新增

- v1 上线就绪：脚手架 / 配置 / 日志 / db / ORM / Alembic / reminder_policy / 阿里云 Channel / Mock /
  订阅 / 退订 / 我的订阅 / 调度 / 通知扇出 / 管理员后台 / Dockerfile / seed_demo / 复核 watchdog /
  PII 清理。

[Unreleased]: https://github.com/growdu/kaoshile/compare/v0.6.0...HEAD
[v0.6.0]: https://github.com/growdu/kaoshile/compare/v0.5.0...v0.6.0
[v0.5.0]: https://github.com/growdu/kaoshile/compare/v0.4.0...v0.5.0
[v0.4.0]: https://github.com/growdu/kaoshile/compare/v0.3.0...v0.4.0
[v0.3.0]: https://github.com/growdu/kaoshile/compare/v0.2.0...v0.3.0
[v0.2.0]: https://github.com/growdu/kaoshile/compare/v0.1.0...v0.2.0
[v0.1.0]: https://github.com/growdu/kaoshile/releases/tag/v0.1.0