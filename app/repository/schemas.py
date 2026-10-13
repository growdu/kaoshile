"""API 用 Pydantic schema。

ORM 模型 → Pydantic → JSON；不直接返回 ORM 以避免泄露内部字段。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.repository.orm import ExamStatus


class ExamOut(BaseModel):
    """考试对外暴露。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    organizer: Optional[str] = None
    registration_start: datetime
    registration_end: datetime
    payment_end: Optional[datetime] = None
    admission_ticket_start: Optional[datetime] = None
    exam_date: datetime
    official_url: Optional[str] = None
    status: ExamStatus


class ExamListResponse(BaseModel):
    """考试列表响应（含分页元信息）。"""

    items: list[ExamOut]
    total: int
    limit: int
    offset: int


class CreateSubscriptionIn(BaseModel):
    """订阅创建输入。"""

    exam_id: int = Field(..., gt=0)
    email: str = Field(..., min_length=3, max_length=200)
    phone: str = Field(..., min_length=11, max_length=20)
    level: str = Field(default="standard")
    channels: list[str] = Field(default_factory=lambda: ["email", "sms"])


class CreateSubscriptionOut(BaseModel):
    """订阅创建输出（pending）。"""

    model_config = ConfigDict(from_attributes=True)

    subscription_id: str
    status: str
    confirm_url: str
    cancel_url: str
    send_times: dict[str, list[datetime]]


class ConfirmSubscriptionOut(BaseModel):
    """确认订阅输出。"""

    subscription_id: str
    status: str
    confirmed_at: datetime


class CancelIn(BaseModel):
    """退订输入（body）。"""

    token: str = Field(..., min_length=1)


class CancelOut(BaseModel):
    """退订输出。"""

    subscription_id: str
    status: str
    cancelled_at: datetime


class MySubscriptionsIn(BaseModel):
    """我的订阅查询输入。"""

    email: str
    token: str


class SubscriptionOut(BaseModel):
    """订阅对外暴露（不含 token）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    exam_id: int
    email: str
    phone: str
    reminder_level: str
    channels: list[str]
    status: str
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class MySubscriptionsOut(BaseModel):
    items: list[SubscriptionOut]


class ErrorOut(BaseModel):
    code: str
    message: str


class EnvelopeOk(BaseModel):
    """成功响应信封（统一）。"""

    ok: bool = True
    data: dict


class EnvelopeErr(BaseModel):
    """错误响应信封。"""

    ok: bool = False
    error: ErrorOut
