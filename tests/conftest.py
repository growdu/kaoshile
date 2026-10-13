"""测试全局 fixture 与配置。

按实现方案 §11.1，每个里程碑添加 fixture 在此。
"""
import os

# 在导入 app 之前把测试环境变量设好，避免 pydantic-settings 读到宿主机 .env
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LINK_SECRET", "test-secret-must-be-32-bytes-or-more-for-hs256")
os.environ.setdefault("MANAGE_PASSWORD_HASH", "$2b$12$dummyhashplaceholderfortests....................")
