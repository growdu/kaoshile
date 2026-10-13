# syntax=docker/dockerfile:1.7
# 考试通知软件 kaoshile — 单容器部署
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# 系统依赖（健康检查 + tzdata + curl）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（缓存层）
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install . \
    && pip install ".[aliyun]" || true

# 拷贝代码
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY alembic.ini ./
COPY docs ./docs
COPY .env.example ./

# 数据目录
RUN mkdir -p /app/data

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1

# 入口：先迁移再启动（生产部署建议用独立 migrate 步骤；这里合并简化）
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
