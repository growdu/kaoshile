"""kaoshile — 考试通知软件。

顶层包。子模块见：
- app.config: 配置层（pydantic-settings）
- app.infra: 基础设施（日志、时间、数据库）
- app.domain: 领域层（纯函数、token、提醒策略）
- app.usecase: 业务用例编排
- app.repository: 数据访问
- app.notification: 通知通道抽象与实现
- app.scheduler: APScheduler 调度器
- app.api: FastAPI 路由
"""

__version__ = "0.1.0"
