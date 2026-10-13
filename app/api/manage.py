"""管理员 API：登录 / 考试 CRUD / 订阅查询 / 通知日志查询 / 健康。

鉴权：Bearer admin_token（HMAC）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infra.db import get_db
from app.repository.exam_repo import ExamRepository
from app.repository.models import Exam, NotificationLog, Subscription
from app.repository.orm import ExamStatus
from app.usecase.admin import AdminAuthError, AdminAuthService

router = APIRouter()


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"ok": False, "error": {"code": code, "message": message}},
    )


def _require_admin(authorization: Optional[str]) -> dict:
    """鉴权并返回 admin payload。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise _err("unauthorized", "missing bearer token", 401)
    token = authorization.split(" ", 1)[1]
    try:
        return AdminAuthService().require_admin(token)
    except AdminAuthError as e:
        raise _err(e.code, e.message, 401)


# ---------- Schemas ----------


class LoginIn(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginOut(BaseModel):
    token: str
    expires_in_days: int


class AdminExamOut(BaseModel):
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
    source_url: str
    last_verified_at: Optional[datetime] = None
    verifier: Optional[str] = None
    status: ExamStatus


class CreateExamIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=50)
    organizer: Optional[str] = Field(None, max_length=200)
    registration_start: datetime
    registration_end: datetime
    payment_end: Optional[datetime] = None
    admission_ticket_start: Optional[datetime] = None
    exam_date: datetime
    official_url: Optional[str] = Field(None, max_length=500)
    source_url: str = Field(..., min_length=1, max_length=500)
    status: ExamStatus = ExamStatus.open


class UpdateExamStatusIn(BaseModel):
    status: ExamStatus


class VerifyExamIn(BaseModel):
    source_hash: Optional[str] = None


class AdminSubOut(BaseModel):
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


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subscription_id: str
    exam_id: int
    node_type: str
    channel: str
    status: str
    attempt_count: int
    vendor_receipt_id: Optional[str]
    error_message: Optional[str]
    sent_at: Optional[datetime] = None


# ---------- 端点 ----------


@router.post("/api/manage/login", tags=["manage"])
def login(payload: LoginIn) -> dict:
    try:
        token = AdminAuthService().authenticate(payload.username, payload.password)
    except AdminAuthError as e:
        raise _err(e.code, e.message, 401)
    return {
        "ok": True,
        "data": LoginOut(
            token=token, expires_in_days=AdminAuthService.TOKEN_TTL_DAYS
        ).model_dump(),
    }


@router.get("/api/manage/exams", tags=["manage"])
def list_exams_admin(
    q: Optional[str] = None,
    status: Optional[ExamStatus] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    _require_admin(authorization)
    repo = ExamRepository(db)
    items, total = repo.list(q=q, status=status, limit=limit, offset=offset)
    return {
        "ok": True,
        "data": {
            "items": [AdminExamOut.model_validate(e).model_dump(mode="json") for e in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.post("/api/manage/exams", tags=["manage"])
def create_exam(
    payload: CreateExamIn,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    _require_admin(authorization)
    exam = Exam(
        name=payload.name,
        category=payload.category,
        organizer=payload.organizer,
        registration_start=payload.registration_start,
        registration_end=payload.registration_end,
        payment_end=payload.payment_end,
        admission_ticket_start=payload.admission_ticket_start,
        exam_date=payload.exam_date,
        official_url=payload.official_url,
        source_url=payload.source_url,
        status=payload.status,
    )
    db.add(exam)
    db.flush()
    return {
        "ok": True,
        "data": AdminExamOut.model_validate(exam).model_dump(mode="json"),
    }


@router.post("/api/manage/exams/{exam_id}/verify", tags=["manage"])
def verify_exam(
    exam_id: int,
    payload: VerifyExamIn,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    """管理员点击「复核」按钮：更新 last_verified_at。"""
    payload_admin = _require_admin(authorization)
    repo = ExamRepository(db)
    exam = repo.get(exam_id)
    if exam is None:
        raise _err("exam_not_found", f"exam {exam_id} not found", 404)
    repo.update_verification(
        exam,
        source_hash=payload.source_hash,
        verifier=payload_admin["username"],
    )
    return {
        "ok": True,
        "data": AdminExamOut.model_validate(exam).model_dump(mode="json"),
    }


@router.patch("/api/manage/exams/{exam_id}/status", tags=["manage"])
def update_exam_status(
    exam_id: int,
    payload: UpdateExamStatusIn,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    _require_admin(authorization)
    repo = ExamRepository(db)
    exam = repo.get(exam_id)
    if exam is None:
        raise _err("exam_not_found", f"exam {exam_id} not found", 404)
    exam.status = payload.status
    db.flush()
    return {
        "ok": True,
        "data": AdminExamOut.model_validate(exam).model_dump(mode="json"),
    }


@router.get("/api/manage/subscriptions", tags=["manage"])
def list_subscriptions_admin(
    exam_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    _require_admin(authorization)
    stmt = select(Subscription)
    count_stmt = select(func.count()).select_from(Subscription)
    if exam_id is not None:
        stmt = stmt.where(Subscription.exam_id == exam_id)
        count_stmt = count_stmt.where(Subscription.exam_id == exam_id)
    if status is not None:
        stmt = stmt.where(Subscription.status == status)
        count_stmt = count_stmt.where(Subscription.status == status)

    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(Subscription.created_at.desc()).limit(limit).offset(offset)
    items = list(db.execute(stmt).scalars().all())
    return {
        "ok": True,
        "data": {
            "items": [AdminSubOut.model_validate(s).model_dump(mode="json") for s in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/api/manage/notifications", tags=["manage"])
def list_notifications_admin(
    exam_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    _require_admin(authorization)
    stmt = select(NotificationLog)
    count_stmt = select(func.count()).select_from(NotificationLog)
    if exam_id is not None:
        stmt = stmt.where(NotificationLog.exam_id == exam_id)
        count_stmt = count_stmt.where(NotificationLog.exam_id == exam_id)
    if status is not None:
        stmt = stmt.where(NotificationLog.status == status)
        count_stmt = count_stmt.where(NotificationLog.status == status)

    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(NotificationLog.id.desc()).limit(limit).offset(offset)
    items = list(db.execute(stmt).scalars().all())
    return {
        "ok": True,
        "data": {
            "items": [NotificationOut.model_validate(n).model_dump(mode="json") for n in items],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/api/manage/health", tags=["manage"])
def admin_health(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    """管理员健康信息。"""
    _require_admin(authorization)
    exams_total = db.execute(select(func.count()).select_from(Exam)).scalar_one()
    subs_total = db.execute(select(func.count()).select_from(Subscription)).scalar_one()
    notif_status_counts = dict(
        db.execute(
            select(NotificationLog.status, func.count()).group_by(NotificationLog.status)
        ).all()
    )
    return {
        "ok": True,
        "data": {
            "exams_total": exams_total,
            "subscriptions_total": subs_total,
            "notifications_by_status": notif_status_counts,
        },
    }
