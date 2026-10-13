"""Alembic 环境配置。

约定：
- 使用 SQLAlchemy 2.x 同步 engine；
- 数据库 URL 从 app.config.Settings 读取（不在 alembic.ini 写死）；
- target_metadata 指向 Base.metadata（含全部模型）。
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.repository.orm import Base
from app.repository.models import Exam, NotificationLog, Subscription  # noqa: F401

# this is the Alembic Config object
config = context.config

# 从 Settings 注入 sqlalchemy.url（避免在 alembic.ini 写真实凭据）
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 元数据用于 autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：仅 URL，不创建 engine。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite 兼容
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：创建 engine 并连接。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite 兼容
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
