"""ORM 模型基类与枚举。

具体模型（Exam / Subscription / NotificationLog）见本目录其他文件，
保持每个文件 < 300 行、单一职责。
"""
from __future__ import annotations

import enum

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的共同基类。"""


class ExamStatus(str, enum.Enum):
    """考试生命周期状态。"""

    draft = "draft"  # 草稿（不展示、不可订阅）
    open = "open"  # 开放订阅
    registration_closed = "registration_closed"  # 报名截止
    archived = "archived"  # 归档（历史）


class SubscriptionStatus(str, enum.Enum):
    """订阅生命周期状态。"""

    pending = "pending"  # 已留联系方式，待用户确认
    active = "active"  # 已确认，会收提醒
    cancelled = "cancelled"  # 已退订


class NodeType(str, enum.Enum):
    """考试关键节点。

    对应数据库列 exam 的 5 个 datetime 字段之一：
    - registration_start  → Exam.registration_start
    - registration_end    → Exam.registration_end
    - payment_end         → Exam.payment_end
    - admission_start     → Exam.admission_ticket_start
    - exam_day            → Exam.exam_date
    """

    registration_start = "registration_start"
    registration_end = "registration_end"
    payment_end = "payment_end"
    admission_start = "admission_start"
    exam_day = "exam_day"


class NotificationStatus(str, enum.Enum):
    """通知发送状态。"""

    queued = "queued"
    sent = "sent"
    failed = "failed"


class NotificationChannel(str, enum.Enum):
    """通知通道。"""

    email = "email"
    sms = "sms"
