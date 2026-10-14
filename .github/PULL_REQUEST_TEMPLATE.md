## 概述

<!-- 一句话描述这次 PR 解决什么问题 / 引入什么能力。 -->

## 关联

<!-- 关联 issue / 文档章节：-->

- Closes #
- Doc: docs/...

## 变更类型

<!-- 勾选所有适用项 -->

- [ ] 新功能（非破坏性）
- [ ] 破坏性变更（需要迁移 / 升级指南）
- [ ] Bug 修复
- [ ] 重构（无行为变化）
- [ ] 文档
- [ ] 测试 / CI

## 测试

<!-- 按用户偏好，每个 commit 必须配套单测 + 集测 -->

- [ ] 新增单元测试（覆盖新增 / 修改模块的 happy + 失败路径）
- [ ] 新增 / 更新集成测试（如 API / 调度变更）
- [ ] `pytest` 本地全绿（**必须**）
- [ ] `scripts/smoke.py` 本地跑通（**必须**）
- [ ] 如覆盖率下降，附理由

## 文档

- [ ] 更新 `docs/requirements.md` / `docs/design.md` / `docs/implementation.md`（如 API / 行为变化）
- [ ] 更新 `docs/user_manual.md`（如面向用户的接口变化）
- [ ] 更新 `CHANGELOG.md`（如有用户可感知变化）

## 检查清单

- [ ] 单文件不超过 ~300 行
- [ ] 函数不超过 ~50 行，缩进 ≤ 3 层
- [ ] commit message 形如 `Vxxx: 说明`
- [ ] 无敏感字段（access_key / secret / phone / email / password / link_secret）出现在日志或 PR 描述
- [ ] 我已阅读并同意 `CONTRIBUTING.md`（如存在）