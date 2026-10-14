"""NotificationLog 数据访问层。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repository.models import NotificationLog
from app.repository.orm import NodeType, NotificationChannel, NotificationStatus


class NotificationLogRepository:
    """NotificationLog CRUD 与调度查询。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, log_id: str) -> Optional[NotificationLog]:
        return self.session.get(NotificationLog, log_id)

    def find(
        self,
        *,
        subscription_id: str,
        node_type: NodeType,
        channel: NotificationChannel,
    ) -> Optional[NotificationLog]:
        return self.session.execute(
            select(NotificationLog).where(
                NotificationLog.subscription_id == subscription_id,
                NotificationLog.node_type == node_type,
                NotificationLog.channel == channel,
            )
        ).scalar_one_or_none()

    def exists(
        self,
        *,
        subscription_id: str,
        node_type: NodeType,
        channel: NotificationChannel,
    ) -> bool:
        return self.find(
            subscription_id=subscription_id, node_type=node_type, channel=channel
        ) is not None

    def insert_queued(
        self,
        *,
        subscription_id: str,
        exam_id: int,
        node_type: NodeType,
        channel: NotificationChannel,
    ) -> NotificationLog:
        import uuid

        log = NotificationLog(
            id=str(uuid.uuid4()),
            subscription_id=subscription_id,
            exam_id=exam_id,
            node_type=node_type,
            channel=channel,
            status=NotificationStatus.queued,
            attempt_count=0,
        )
        self.session.add(log)
        self.session.flush()
        return log

    def mark_sent(self, log: NotificationLog, *, receipt_id: str) -> None:
        log.status = NotificationStatus.sent
        log.vendor_receipt_id = receipt_id
        log.attempt_count = log.attempt_count + 1
        log.sent_at = datetime.utcnow()
        self.session.flush()

    def mark_failed(
        self, log: NotificationLog, *, error: str, increment: bool = True
    ) -> None:
        log.status = NotificationStatus.failed
        log.error_message = error
        if increment:
            log.attempt_count = log.attempt_count + 1
        self.session.flush()
