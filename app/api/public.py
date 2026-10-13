"""公共 API：考试目录 / 订阅 / 退订 / 我的订阅。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.domain.tokens import InvalidToken
from app.infra.db import get_db
from app.repository.exam_repo import ExamRepository
from app.repository.orm import ExamStatus
from app.repository.schemas import (
    CancelIn,
    ConfirmSubscriptionOut,
    CreateSubscriptionIn,
    CreateSubscriptionOut,
    EnvelopeOk,
    ExamListResponse,
    ExamOut,
    MySubscriptionsOut,
    SubscriptionOut,
)
from app.repository.subscription_repo import SubscriptionRepository
from app.usecase.subscription import SubscriptionError, SubscriptionService
from app.usecase.notification import NotificationService

router = APIRouter()


def _service(db: Session) -> SubscriptionService:
    notifier = NotificationService()
    return SubscriptionService(
        ExamRepository(db),
        SubscriptionRepository(db),
        notifier=notifier,
    )


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"ok": False, "error": {"code": code, "message": message}},
    )


# ---------- 考试目录 ----------


@router.get("/api/exams", response_model=EnvelopeOk, tags=["public"])
def list_exams(
    q: Optional[str] = Query(None, description="按名称子串过滤"),
    category: Optional[str] = Query(None),
    status: Optional[ExamStatus] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    repo = ExamRepository(db)
    items, total = repo.list(q=q, category=category, status=status, limit=limit, offset=offset)
    return {
        "ok": True,
        "data": ExamListResponse(
            items=[ExamOut.model_validate(e) for e in items],
            total=total,
            limit=limit,
            offset=offset,
        ).model_dump(mode="json"),
    }


@router.get("/api/exams/{exam_id}", response_model=EnvelopeOk, tags=["public"])
def get_exam(exam_id: int, db: Session = Depends(get_db)) -> dict:
    repo = ExamRepository(db)
    exam = repo.get(exam_id)
    if exam is None:
        raise _err("exam_not_found", f"exam {exam_id} not found", 404)
    return {
        "ok": True,
        "data": ExamOut.model_validate(exam).model_dump(mode="json"),
    }


# ---------- 订阅 ----------


@router.post("/api/subscriptions", response_model=EnvelopeOk, tags=["public"])
def create_subscription(payload: CreateSubscriptionIn, db: Session = Depends(get_db)) -> dict:
    svc = _service(db)
    try:
        sub, exam, send_times = svc.create(
            exam_id=payload.exam_id,
            email=payload.email,
            phone=payload.phone,
            level=payload.level,
            channels=payload.channels,
        )
    except SubscriptionError as e:
        raise _err(e.code, e.message, 400)

    out = CreateSubscriptionOut(
        subscription_id=sub.id,
        status=sub.status.value,
        confirm_url=f"/c/{sub.confirm_token}",
        cancel_url=f"/s/{sub.cancel_token}",
        send_times=send_times,
    )
    return {"ok": True, "data": out.model_dump(mode="json")}


@router.get("/api/subscriptions/confirm", response_model=EnvelopeOk, tags=["public"])
def confirm_subscription(
    token: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    svc = _service(db)
    try:
        sub = svc.confirm(token)
    except InvalidToken as e:
        raise _err("invalid_token", str(e), 400)
    except SubscriptionError as e:
        raise _err(e.code, e.message, 400)
    out = ConfirmSubscriptionOut(
        subscription_id=sub.id,
        status=sub.status.value,
        confirmed_at=sub.confirmed_at,  # type: ignore[arg-type]
    )
    return {"ok": True, "data": out.model_dump(mode="json")}


@router.post("/api/subscriptions/cancel", response_model=EnvelopeOk, tags=["public"])
def cancel_subscription(payload: CancelIn, db: Session = Depends(get_db)) -> dict:
    svc = _service(db)
    try:
        sub = svc.cancel(payload.token)
    except InvalidToken as e:
        raise _err("invalid_token", str(e), 400)
    except SubscriptionError as e:
        raise _err(e.code, e.message, 400)
    return {
        "ok": True,
        "data": {
            "subscription_id": sub.id,
            "status": sub.status.value,
            "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
        },
    }


@router.get("/api/subscriptions/me", response_model=EnvelopeOk, tags=["public"])
def my_subscriptions(
    email: str = Query(..., min_length=3),
    token: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    """通过 email + token 查看我的订阅。

    token 应为最新一次 confirm 或 cancel token 中任意一个（验证其 email 匹配）。
    """
    from app.domain.tokens import verify

    try:
        payload = verify(token)
    except InvalidToken as e:
        raise _err("invalid_token", str(e), 400)
    sub_repo = SubscriptionRepository(db)
    sub = sub_repo.get(payload.get("sub_id", ""))
    if sub is None:
        raise _err("invalid_token", "subscription not found", 400)
    if sub.email.lower() != email.lower():
        raise _err("invalid_token", "email mismatch", 400)

    items = [
        SubscriptionOut.model_validate(s)
        for s in sub_repo.find_by_email(email)
    ]
    return {"ok": True, "data": {"items": [i.model_dump(mode="json") for i in items]}}
