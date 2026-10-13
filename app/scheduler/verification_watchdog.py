"""复核 watchdog：把长期未复核的考试自动置 draft。

约定：
- 每天跑一次；
- 阈值来自 Settings.verification_expire_days（默认 90）；
- last_verified_at 为 None 的考试视作从创建起算（用 created_at）；
- 触发后将 status 改为 draft 并记 audit 日志。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.infra.logging import get_logger
from app.repository.models import Exam
from app.repository.orm import ExamStatus

log = get_logger(__name__)


def run(session_factory: Callable[[], Session]) -> int:
    """扫描并自动过期长期未复核的考试。Returns: 置为 draft 的数量。"""
    settings = get_settings()
    expire_threshold = timedelta(days=settings.verification_expire_days)
    now = datetime.utcnow()

    count = 0
    with session_factory() as session:
        candidates = list(
            session.execute(
                select(Exam).where(Exam.status == ExamStatus.open)
            ).scalars().all()
        )
        for exam in candidates:
            reference = exam.last_verified_at or exam.created_at
            if reference is None or (now - reference) < expire_threshold:
                continue
            log.warning(
                "verification_expired",
                exam_id=exam.id,
                name=exam.name,
                last_verified_at=reference.isoformat() if reference else None,
            )
            exam.status = ExamStatus.draft
            count += 1
        session.commit()
    return count
