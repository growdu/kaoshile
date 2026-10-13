"""数据看板 API：订阅热度 / 节点漏斗 / 发送成功率。

仅管理员可见；基于已有 ORM 表做聚合。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infra.db import get_db
from app.repository.models import Exam, NotificationLog, Subscription
from app.repository.orm import ExamStatus, SubscriptionStatus

from app.api.manage import _require_admin

router = APIRouter()


@router.get("/api/manage/dashboard/overview", tags=["manage", "dashboard"])
def overview(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    """总览：考试 / 订阅 / 通知 三态计数。"""
    _require_admin(authorization)
    exams_total = db.execute(select(func.count()).select_from(Exam)).scalar_one()
    subs_total = db.execute(select(func.count()).select_from(Subscription)).scalar_one()
    subs_active = db.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.status == SubscriptionStatus.active
        )
    ).scalar_one()
    notif_by_status = dict(
        db.execute(
            select(NotificationLog.status, func.count()).group_by(NotificationLog.status)
        ).all()
    )
    return {
        "ok": True,
        "data": {
            "exams_total": exams_total,
            "subscriptions_total": subs_total,
            "subscriptions_active": subs_active,
            "notifications_by_status": notif_by_status,
        },
    }


@router.get("/api/manage/dashboard/exam-heatmap", tags=["manage", "dashboard"])
def exam_heatmap(
    limit: int = 10,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    """订阅热度：每个考试的 active 订阅数 top N。"""
    _require_admin(authorization)
    stmt = (
        select(
            Exam.id,
            Exam.name,
            Exam.category,
            func.count(Subscription.id).label("subs"),
        )
        .join(Subscription, Subscription.exam_id == Exam.id, isouter=False)
        .where(Subscription.status == SubscriptionStatus.active)
        .group_by(Exam.id, Exam.name, Exam.category)
        .order_by(func.count(Subscription.id).desc())
        .limit(limit)
    )
    rows = [
        {"exam_id": eid, "name": name, "category": cat, "active_subs": subs}
        for eid, name, cat, subs in db.execute(stmt).all()
    ]
    return {"ok": True, "data": {"items": rows}}


@router.get("/api/manage/dashboard/notification-success-rate", tags=["manage", "dashboard"])
def notification_success_rate(
    days: int = 7,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    """发送成功率：最近 N 天 sent / (sent+failed) 比例。"""
    _require_admin(authorization)
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = db.execute(
        select(NotificationLog.status, func.count())
        .where(NotificationLog.sent_at >= cutoff)
        .group_by(NotificationLog.status)
    ).all()
    by_status = dict(rows)
    sent = by_status.get("sent", 0)
    failed = by_status.get("failed", 0)
    total = sent + failed
    rate = (sent / total) if total > 0 else 1.0
    return {
        "ok": True,
        "data": {
            "window_days": days,
            "sent": sent,
            "failed": failed,
            "success_rate": round(rate, 4),
        },
    }


@router.get("/api/manage/dashboard/stale-exams", tags=["manage", "dashboard"])
def stale_exams(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    """过期考试：last_verified_at > 30 天。"""
    _require_admin(authorization)
    cutoff = datetime.utcnow() - timedelta(days=30)
    rows = list(
        db.execute(
            select(Exam.id, Exam.name, Exam.last_verified_at, Exam.verifier)
            .where(Exam.status == ExamStatus.open, Exam.last_verified_at < cutoff)
            .order_by(Exam.last_verified_at.asc())
            .limit(100)
        ).all()
    )
    return {
        "ok": True,
        "data": {
            "items": [
                {
                    "exam_id": eid,
                    "name": name,
                    "last_verified_at": lv.isoformat() if lv else None,
                    "verifier": verifier,
                }
                for eid, name, lv, verifier in rows
            ]
        },
    }
