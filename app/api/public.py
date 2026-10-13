"""公共 API：考试目录 / 订阅 / 退订（无需管理鉴权）。

所有响应统一信封：{"ok": true, "data": ...} 或 {"ok": false, "error": {...}}。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.infra.db import get_db
from app.repository.exam_repo import ExamRepository
from app.repository.orm import ExamStatus
from app.repository.schemas import (
    CancelIn,
    CancelOut,
    ConfirmSubscriptionOut,
    CreateSubscriptionIn,
    CreateSubscriptionOut,
    EnvelopeErr,
    EnvelopeOk,
    ExamListResponse,
    ExamOut,
    MySubscriptionsIn,
    MySubscriptionsOut,
    SubscriptionOut,
)

router = APIRouter()


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
        raise HTTPException(status_code=404, detail={"ok": False, "error": {"code": "exam_not_found", "message": f"exam {exam_id} not found"}})
    return {
        "ok": True,
        "data": ExamOut.model_validate(exam).model_dump(mode="json"),
    }
