# 最佳实践

> 版本：**v7.0**（2026-10-14）
> 维护者：Mavis

本文档面向**参与本项目的开发者与运维**，聚合「kaoshile 项目惯例 + 跨项目通用工程实践」。

适用边界：

- 项目惯例章节（§1-§4）只对 kaoshile 项目生效；
- 通用实践章节（§5-§10）适用于大多数 Python 后端 / Web 服务项目；
- 涉及具体业务规则请回到 [`requirements.md`](./requirements.md) / [`design.md`](./design.md)；
- 用户面向的接口用法在 [`user_manual.md`](./user_manual.md)。

---

## 1. 提交与版本节奏

> 来自用户长期偏好（已写入 user memory）。

### 1.1 规则

1. **每个子模块完成立即 commit**——不攒 commit；
2. **每个 commit 必须配套**：
   - 新模块的单元测试（happy + 至少 1 个失败路径）；
   - 若引入 / 修改 API 或调度行为，对应集成测试；
   - 所有新增测试在本地 `pytest` 全绿；
3. **代码可测试、可回溯、简单易懂**：
   - 单文件不超过 ~300 行（超过即拆）；
   - 函数不超过 ~50 行（超过即拆）；
   - 函数最多 3 层缩进；
   - 每个 PR / commit 描述包含「为什么」与「测试覆盖了什么」。

### 1.2 Commit message 模板

```
V<n>.<m>: <一句话能力描述（动词开头，30 字内）>

<动机 / 关联 issue / 文档章节>
<关键设计决策 / 与之前方案的对比>
<测试覆盖了哪些用例>
```

示例：

```
V7.1: CI 补强（release workflow + dependabot + 模板 + CHANGELOG + 9 单测）

- release workflow：打 v* tag 触发全测 + 镜像推 GHCR + 创建 GitHub Release
- dependabot.yml：每周一自动 PR 更新 pip + GitHub Actions 依赖
- CODEOWNERS + Issue/PR 模板：路径级代码审阅 + 标准化提交流程
- tests/unit/test_ci_workflow.py：保证 CI 配置完整可解析
```

### 1.3 版本号约定

遵循 SemVer：

| 类型 | 增量 | 示例 |
| --- | --- | --- |
| 破坏性 | major + 1 | `1.0.0 → 2.0.0`（数据库 schema 不兼容） |
| 新功能 | minor + 1 | `1.2.3 → 1.3.0`（新通道、新接口） |
| 修复 / 重构 | patch + 1 | `1.2.3 → 1.2.4`（bug fix、文案调整） |

每次版本升级：

1. 跑 `alembic upgrade head`（如有迁移）；
2. 更新 `CHANGELOG.md` 的 `[Unreleased]` → `[vX.Y.Z]` 段落；
3. 重新生成并 push `vX.Y.Z` tag；
4. CI 自动跑 release workflow（详见 [`design.md §16`](./design.md#16-ci-与文档自动化设计v6)）。

---

## 2. 测试策略

### 2.1 必备测试矩阵

| 层 | 命名 | 覆盖目标 |
| --- | --- | --- |
| 单元 | `tests/unit/test_<module>.py` | 单函数 / 单类的 happy + 失败路径 |
| 集成 | `tests/integration/test_<feature>_api.py` | 跨模块端到端 |
| 冒烟 | `scripts/smoke.py` | 主链路 in-process 端到端 |

### 2.2 测试隔离

`tests/conftest.py` 必须含 autouse fixture：

```python
@pytest.fixture(autouse=True)
def _reset_module_globals():
    """每个测试后清理模块级单例状态，避免跨测试污染。"""
    yield
    # engine / registry / scheduler / structlog 全部重置
```

任何新增的「全局单例」（cache / counter / clock）必须接入这个 fixture。

### 2.3 关键模块必须 100% 行覆盖

- `reminder_policy` / `tokens` / `notification_service` / `subscription_service`；
- 测试方法：`pytest --cov=app.<module> --cov-report=term`。

### 2.4 不可变行为回归保护

凡被 `tests/unit/test_reminder_policy.py` 等覆盖的关键计算（如 reminder 提前量、token 签发），**禁止**"顺手优化"——改了必须先看测试是否需要更新。

### 2.5 端到端冒烟脚本

`scripts/smoke.py` 必须：

- in-process 启动（不依赖外部 HTTP）；
- 用 in-memory SQLite + MockChannel（不污染生产数据）；
- 8 步主链路 ≤ 5 秒；
- 在 CI 的 `smoke` job 跑通（详见 `design.md §16.2`）。

### 2.6 新增 API 的测试必须断言信封

```python
def test_create_exam_returns_envelope(client):
    r = client.post("/api/manage/exams", json=...)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "data" in r.json()
```

---

## 3. 文档维护

### 3.1 何时更新哪份文档

| 变更类型 | 必须更新 |
| --- | --- |
| 新增 / 修改 API path | `user_manual.md`（`test_user_manual.py` 会自动校验） |
| 架构变更 | `design.md` |
| 需求变更 | `requirements.md` |
| 流程 / 里程碑 | `implementation.md` |
| 用户可感知变更 | `CHANGELOG.md` `[Unreleased]` |
| 新增依赖 | `pyproject.toml` + `requirements.md` §约束 |
| CI 改动 | `design.md §16` + `ci.yml` 完整性测试 |

### 3.2 文档完整性自动校验

CI 通过以下测试保证文档与代码同步：

| 测试 | 验证 |
| --- | --- |
| `test_user_manual.py` | 每个 API path 至少在手册中出现一次 |
| `test_ci_workflow.py` | workflow YAML 可解析 + 必需 job / trigger 都在 |

新增强校验时，**先写测试让它失败，再补文档让它通过**——反向保证流程。

### 3.3 文档行数约束（仅文档）

- 章节内长列表不要超过 ~50 行；
- 大表格改用引用（如 `data_sources.md` 的白名单）。

---

## 4. 安全实践

### 4.1 敏感字段

`access_key` / `secret` / `phone` / `email` / `password` / `token` / `link_secret` 这七类：

- 禁止入库（除业务字段）；
- 禁止出现在日志 / 通知 / commit message / PR 描述；
- 禁止出现在文档（截图 / 示例用占位）；
- 自动脱敏见 `app/infra/logging.py`。

### 4.2 Token 设计

- HMAC-SHA256 签名（不要明文 query string）；
- payload 必含 `action` / `exp`；
- 30 天 TTL（订阅 / 退订）/ 30 分钟 TTL（重置）；
- 密钥 `HMAC_SECRET` / `LINK_SECRET` 通过环境变量注入；**绝不入库**；
- 改密码后所有旧 token 立即失效。

### 4.3 密码

- 用户密码：bcrypt cost ≥ 12；
- 管理员密码：bcrypt 哈希进环境变量；**无自助找回路径**（有意设计）。

### 4.4 鉴权

- 管理后台接口必须 `Authorization: Bearer <admin_token>` 强制鉴权（`require_user` 装饰器）；
- 用户侧 HMAC token 不需要 session（适合邮件 / 短信点击）；
- Bearer token 失败返 401；HMAC token 失败返 400 + `invalid_token`。

### 4.5 注入风险

- SQL：统一走 SQLAlchemy ORM；禁止 `text(f"...{var}...")`；
- 命令：禁止 `subprocess.run(shell=True)`；参数走数组；
- 日志：禁止把用户输入直接拼到日志里。

---

## 5. 性能与可观测

### 5.1 性能基线

- 关键路径 P95 延迟：订阅提交 → 确认邮件 ≤ 5s；
- 调度器扇出：单实例 ≥ 50 条 / 秒；
- 端到端冒烟脚本 ≤ 5s（in-process）。

### 5.2 不要做的事

- 同步阻塞循环里查 DB（用 `selectinload` / `joinedload`）；
- 在 usecase 里 `time.sleep`（用 APScheduler 替代）；
- 任何 `asyncio.run` 嵌套调用（破坏事件循环）；
- 在测试中真实访问网络（除 `conftest.py` 显式 opt-in）。

### 5.3 结构化日志

- 字段：`event` / `level` / `timestamp` + 业务字段（`subscription_id` / `channel` / `node` / `attempt`）；
- 不写：完整 URL、query string、token 头、密码、AK/SK；
- 用 `structlog.get_logger(__name__)` 而非 `logging.getLogger(__name__)`。

### 5.4 健康检查三件套

- `/healthz`：进程存活探针，永远 200；
- `/readyz`：DB / 调度器 / 通道注册表全部就绪才 200；
- `/api/manage/health`：管理员侧的详细状态（DB 连接数、调度器下次触发时间、注册表大小）。

---

## 6. 部署与运维

### 6.1 Docker

- 镜像版本与 `pyproject.toml` `version` 字段保持一致；
- 镜像同时推 `ghcr.io/<owner>/kaoshile:vX.Y.Z` 与 `:latest`；
- 生产侧用 `:vX.Y.Z` 而非 `:latest`（避免误升级）。

### 6.2 反向代理

- Nginx / Envoy / 云 LB 任选；
- 速率限制在反向代理层做（应用层做太晚）；
- `client_max_body_size 1m` 防止恶意上传；
- HTTPS 终端终止在反代（容器内仍 HTTP）。

### 6.3 数据库

- 开发期 SQLite；生产期 PostgreSQL；
- **禁止手动改库**——一切通过 Alembic 迁移；
- 备份：每日全量 + WAL 持续归档（PG）/ `.backup` 文件组（SQLite）；
- 备份**不含 `.env`**。

### 6.4 配置

- 配置分层：默认 < 环境变量 < 配置文件 < 命令行参数；
- 关键配置（HMAC_SECRET / LINK_SECRET / AK / SK）**必须**环境变量，**禁止**入库；
- 启动 fail-fast：缺失关键配置直接报错而不是降级。

### 6.5 升级

详见 [`user_manual.md §7`](./user_manual.md#7-升级流程)。要点：

- 大版本先在 staging 验证；
- 备份数据库；
- 看 CHANGELOG 移除项；
- 滚动重启。

---

## 7. 代码组织

### 7.1 单向依赖：
```
api → usecase → repository → models
   ↘     ↘
    notification / scheduler / domain
```

- `domain` 不依赖任何上层（纯函数 / dataclass）；
- `repository` 只依赖 SQLAlchemy ORM；
- `usecase` 编排 `repository` + `notification` + `scheduler`；
- `api` 只依赖 `usecase`；
- 禁止反向依赖。

### 7.2 模块命名

- `app/<layer>/<concept>.py`：单文件单概念；
- `app/<layer>/<concept>_repo.py`：Repository；
- `app/<layer>/<concept>_service.py`：Service。

### 7.3 抽象与扩展点

- 通知通道：`Channel` Protocol；
- 分布式锁：`DistributedLock` Protocol + InMemoryLock 默认 + RedisLock 占位；
- 模板：`TemplateRenderer` DB 优先 + 默认 fallback；
- 调度：`scan_now` 后置触发，回调委托 NotificationService.dispatch。

新加的扩展点必须有 Protocol + 默认实现 + 测试，不允许直接在业务代码里硬编码。

---

## 8. 数据可靠性

### 8.1 幂等

- 同一 (订阅, 节点, 通道) 在 `NotificationLog` DB 唯一约束；
- 通知重试 3 次（1s / 5s / 25s），最终失败标记 `failed`；
- 邮件 / 短信 / 数据库插入都用 `try + raise_with_from` 显式失败路径。

### 8.2 复核

- 每条考试 `last_verified_at`：> 30 天告警，> 90 天自动 draft；
- `source_hash`：公告 SHA-256 变更检测（解析助手用）；
- 受限 Fetcher 仅对 `data_sources.md` 白名单源生效。

### 8.3 PII 清理

- 退订 7 天后清空邮箱 / 手机号字段；
- 清空前保留订阅主记录（id / 节点哈希 / 状态）便于审计；
- 清理 job 由 `app/scheduler/pii_cleanup.py` 每日跑。

---

## 9. 反模式（不要做）

| 反模式 | 后果 | 正确做法 |
| --- | --- | --- |
| 在 commit 里塞大文件 / 重命名 | 难 review | 拆 commit |
| `try: ... except: pass` | 吞错 | 至少 log + raise |
| 全局可变状态 | 测试难 | 单例需可重置（conftest 接管） |
| 时间字段用 naive datetime | DST / tz bug | 一律 tz-aware Asia/Shanghai |
| 凭据字典直读数据库 | 入侵数据 | 用 `app/config.py` + 环境变量 |
| 在循环里查 N 次 DB | N+1 | `selectinload` / `joinedload` |
| 在测试里真发邮件 / 短信 | 污染 + 慢 | MockChannel |
| 在 usecase 里写 HTTP 客户端 | 慢测 + 难 mock | 抽 Protocol |
| 文档和实现不同步 | 误导 | CI 校验；先写测试失败再补文档 |
| 长函数 / 长文件 | 难维护 | 拆；300 行 / 50 行 / 3 层缩进 |

---

## 10. 跨项目可复用的工程实践

下面这些实践不限于本项目，建议在多数 Python 后端 / Web 服务项目都遵循：

### 10.1 测试先于实现（TDD）

对核心业务规则（reminder_policy / token 签发 / 通知扇出）：

1. 先写测试让它失败；
2. 实现让它通过；
3. 重构保持通过。

### 10.2 文档与代码同步

- 每次 PR 至少检查「我改了哪些文档」；
- CI 用静态测试（`test_user_manual.py` 等）兜底，但**人在 review 时也要看**。

### 10.3 提交节奏

- 每个子模块完成立即 commit；
- 每个 commit 配单测；
- 不攒 commit（攒到 30 个文件一起提往往一塌糊涂）。

### 10.4 可逆性

- 数据库迁移**单向**要支持 downgrade（除非数据迁移不可逆）；
- 环境变量变更**先备好回滚命令**再执行；
- 删除代码**先 git 提交**再删——保留历史。

### 10.5 12-factor 原则

代码 / 配置分离；日志到 stdout；环境变量管配置；一个进程一个职责；构建 / 发布 / 运行分离。

### 10.6 守门而不是放行：
- CI lint 默认 fail-fast；
- 测试覆盖率 < 60% 阻断 merge；
- 文档完整性测试必须在 CI 跑。

### 10.7 远离魔法

- 拒绝「运行时修改模块变量」；
- 拒绝「隐式全局状态」；
- 拒绝「配置文件里塞 callback 函数」。

---

> 文档结束。任何工程实践争议先在本文件末尾追加「决策记录」段落，再去改代码。