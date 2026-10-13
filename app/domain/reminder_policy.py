"""提醒提前量策略。

根据考试关键节点与用户选择的提醒档位（保守/标准/强烈），推导所有需要发送通知的时刻。

设计原则（见 docs/requirements.md §4.3）：
- 纯函数：输入是 Exam 字段（ducktype），输出是 dict[NodeType, list[datetime]]；
- 输出统一 Asia/Shanghai tz-aware；
- 缺失字段（payment_end / admission_ticket_start 为可空）跳过该节点。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol

from app.infra.time import TZ_SHANGHAI

# 节点类型 → Exam 字段名
NODE_FIELD: dict[str, str] = {
    "registration_start": "registration_start",
    "registration_end": "registration_end",
    "payment_end": "payment_end",
    "admission_start": "admission_ticket_start",
    "exam_day": "exam_date",
}

# 档位 → 节点 → 提前量（天；负数表示提前；0 表示节点时刻本身）
POLICIES: dict[str, dict[str, list[int]]] = {
    "conservative": {
        "registration_start": [-1],
        "registration_end": [-1],
        "payment_end": [-1],
        "admission_start": [-1],
        "exam_day": [-3],
    },
    "standard": {
        "registration_start": [-1],
        "registration_end": [-3, -1],
        "payment_end": [-3, -1],
        "admission_start": [-1],
        "exam_day": [-7, -3, -1],
    },
    "aggressive": {
        "registration_start": [-1],
        "registration_end": [-7, -3, -1],
        "payment_end": [-7, -3, -1],
        "admission_start": [-3, -1],
        "exam_day": [-14, -7, -3, -1],
    },
}

VALID_LEVELS = frozenset(POLICIES.keys())


class ExamLike(Protocol):
    """ducktype：任何含 5 个时间字段的对象。"""

    registration_start: datetime | None
    registration_end: datetime | None
    payment_end: datetime | None
    admission_ticket_start: datetime | None
    exam_date: datetime | None


def _as_shanghai(dt: datetime) -> datetime:
    """把任意 datetime 转 tz-aware Asia/Shanghai。naive 视为 UTC。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=__import__("datetime").timezone.utc)
    return dt.astimezone(TZ_SHANGHAI)


def compute_send_times(exam: ExamLike, level: str) -> dict[str, list[datetime]]:
    """推导所有需要发送通知的时刻。

    Args:
        exam: 含 5 个时间字段的对象（ORM Exam / dataclass / dict 都可）
        level: 提醒档位，必须在 VALID_LEVELS 中

    Returns:
        dict[node_type, list[datetime]]，datetime 均为 tz-aware Asia/Shanghai。
        缺失字段对应的节点不会出现在结果中。
    """
    if level not in VALID_LEVELS:
        raise ValueError(f"invalid reminder level: {level!r}; expected one of {sorted(VALID_LEVELS)}")

    policy = POLICIES[level]
    out: dict[str, list[datetime]] = {}
    for node, offsets in policy.items():
        field = NODE_FIELD[node]
        base = getattr(exam, field, None)
        if base is None:
            continue
        base_sha = _as_shanghai(base)
        out[node] = [base_sha + timedelta(days=off) for off in offsets]
    return out


def get_policy_summary() -> dict[str, dict[str, list[int]]]:
    """返回档位策略的只读快照（用于管理后台展示）。"""
    return {lvl: {node: list(offs) for node, offs in pol.items()} for lvl, pol in POLICIES.items()}


def exam_node_value(exam: Any, node: str) -> datetime | None:
    """根据节点名读取 Exam 上对应 datetime 字段（未设置返回 None）。"""
    field = NODE_FIELD.get(node)
    if field is None:
        raise ValueError(f"unknown node: {node!r}")
    return getattr(exam, field, None)
