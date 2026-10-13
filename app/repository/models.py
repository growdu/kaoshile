"""ORM 模型：Exam / Subscription / NotificationLog。

约定：
- 所有 datetime 入库统一 UTC（naive，应用层做时区转换）；
- source_url 是必填（见 data_sources.md §4.2）；
- 唯一约束保证幂等（同一 (sub, node, channel) 只发一次）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.repository.orm import (
    Base,
    ExamStatus,
    NodeType,
    NotificationChannel,
    NotificationStatus,
    SubscriptionStatus,
)


def _utcnow() -> datetime:
    """生成 UTC naive datetime（与 SQLAlchemy DateTime 默认对齐）。"""
    return datetime.utcnow()


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Exam(Base):
    """一场考试的主数据。"""

    __tablename__ = "exam"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))
    organizer: Mapped[str | None] = mapped_column(String(200))

    # 关键时间节点（UTC）
    registration_start: Mapped[datetime] = mapped_column(DateTime)
    registration_end: Mapped[datetime] = mapped_column(DateTime)
    payment_end: Mapped[datetime | None] = mapped_column(DateTime)
    admission_ticket_start: Mapped[datetime | None] = mapped_column(DateTime)
    exam_date: Mapped[datetime] = mapped_column(DateTime)

    # 链接
    official_url: Mapped[str | None] = mapped_column(String(500))

    # 数据可靠性字段（必填录入，见 data_sources.md §4.2）
    source_url: Mapped[str] = mapped_column(String(500))
    source_hash: Mapped[str | None] = mapped_column(String(64))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verifier: Mapped[str | None] = mapped_column(String(50))

    # 状态
    status: Mapped[ExamStatus] = mapped_column(SAEnum(ExamStatus), default=ExamStatus.draft)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_exam_status_reg_end", "status", "registration_end"),
        Index("ix_exam_last_verified_at", "last_verified_at"),
        Index("ix_exam_category", "category"),
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(  # type: ignore[name-defined]
        back_populates="exam", cascade="all, delete-orphan"
    )


class Subscription(Base):
    """一条订阅记录。"""

    __tablename__ = "subscription"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exam.id"))

    # 联系方式（应用层做大小写、格式校验）
    email: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20))

    reminder_level: Mapped[str] = mapped_column(String(20), default="standard")
    channels: Mapped[list[str]] = mapped_column(JSON, default=list)

    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus), default=SubscriptionStatus.pending
    )

    confirm_token: Mapped[str] = mapped_column(String(200), unique=True)
    cancel_token: Mapped[str] = mapped_column(String(200), unique=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint(
            "email", "exam_id", "status", name="uq_sub_email_exam_status"
        ),
        Index("ix_sub_email_status", "email", "status"),
        Index("ix_sub_exam_status", "exam_id", "status"),
    )

    exam: Mapped["Exam"] = relationship(back_populates="subscriptions")
    notifications: Mapped[list["NotificationLog"]] = relationship(  # type: ignore[name-defined]
        back_populates="subscription", cascade="all, delete-orphan"
    )


class NotificationLog(Base):
    """一条通知发送记录（用于幂等与历史查询）。"""

    __tablename__ = "notification_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("subscription.id"))
    exam_id: Mapped[int] = mapped_column(ForeignKey("exam.id"))

    node_type: Mapped[NodeType] = mapped_column(SAEnum(NodeType))
    channel: Mapped[NotificationChannel] = mapped_column(SAEnum(NotificationChannel))
    status: Mapped[NotificationStatus] = mapped_column(
        SAEnum(NotificationStatus), default=NotificationStatus.queued
    )

    attempt_count: Mapped[int] = mapped_column(default=0)
    vendor_receipt_id: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "node_type",
            "channel",
            name="uq_log_sub_node_channel",
        ),
        Index("ix_log_exam_status", "exam_id", "status"),
    )

    subscription: Mapped["Subscription"] = relationship(back_populates="notifications")
