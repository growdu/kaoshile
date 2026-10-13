"""时间工具：统一的 tz-aware 时间函数。

约定：
- 数据库一律存 UTC（naive 或 tz-aware 都行，但代码统一返回 tz-aware UTC）；
- 业务判定（"今天 9:00 发送"）用 Asia/Shanghai；
- 所有 datetime 入库前必须经过 to_utc() 转换。
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

TZ_SHANGHAI: ZoneInfo = ZoneInfo("Asia/Shanghai")
TZ_UTC: ZoneInfo = ZoneInfo("UTC")


def now_utc() -> datetime:
    """返回当前 UTC 时间（tz-aware）。"""
    return datetime.now(TZ_UTC)


def now_shanghai() -> datetime:
    """返回当前 Asia/Shanghai 时间（tz-aware）。"""
    return datetime.now(TZ_SHANGHAI)


def to_utc(dt: datetime) -> datetime:
    """任意 datetime → tz-aware UTC。

    - 若 dt naive：按 Asia/Shanghai 解释（与业务约定一致）；
    - 若 dt tz-aware：原地转 UTC。
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_SHANGHAI)
    return dt.astimezone(TZ_UTC)


def to_shanghai(dt: datetime) -> datetime:
    """任意 datetime → tz-aware Asia/Shanghai。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_UTC)
    return dt.astimezone(TZ_SHANGHAI)


def parse_iso(s: str) -> datetime:
    """解析 ISO8601 字符串为 tz-aware datetime。"""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_SHANGHAI)
    return dt
