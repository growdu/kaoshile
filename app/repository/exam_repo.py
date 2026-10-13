"""Exam 数据访问层。

只做 CRUD 与基础查询，业务规则不放在这里。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.repository.models import Exam
from app.repository.orm import ExamStatus


class ExamRepository:
    """Exam CRUD 与列表查询。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, exam_id: int) -> Optional[Exam]:
        return self.session.get(Exam, exam_id)

    def list(
        self,
        *,
        q: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[ExamStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Exam], int]:
        """返回 (items, total)。

        - q: 按 name 子串过滤（大小写不敏感）；
        - category: 精确匹配；
        - status: 枚举过滤；
        - limit/offset: 分页。
        """
        stmt = select(Exam)
        count_stmt = select(func.count()).select_from(Exam)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(Exam.name.ilike(like))
            count_stmt = count_stmt.where(Exam.name.ilike(like))
        if category:
            stmt = stmt.where(Exam.category == category)
            count_stmt = count_stmt.where(Exam.category == category)
        if status is not None:
            stmt = stmt.where(Exam.status == status)
            count_stmt = count_stmt.where(Exam.status == status)

        total = self.session.execute(count_stmt).scalar_one()
        stmt = stmt.order_by(Exam.registration_start.asc()).limit(limit).offset(offset)
        items = list(self.session.execute(stmt).scalars().all())
        return items, total

    def add(self, exam: Exam) -> Exam:
        self.session.add(exam)
        self.session.flush()
        return exam

    def update_verification(
        self, exam: Exam, *, source_hash: Optional[str] = None, verifier: str
    ) -> None:
        """管理员点击「复核」时调用。"""
        from datetime import datetime

        exam.last_verified_at = datetime.utcnow()
        exam.verifier = verifier
        if source_hash is not None:
            exam.source_hash = source_hash
        self.session.flush()
