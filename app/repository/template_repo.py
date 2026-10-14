"""Template 数据访问层。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repository.models import Template


class TemplateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, template_id: int) -> Optional[Template]:
        return self.session.get(Template, template_id)

    def find_by_name(self, name: str) -> Optional[Template]:
        return self.session.execute(
            select(Template).where(Template.name == name)
        ).scalar_one_or_none()

    def list(self) -> list[Template]:
        return list(
            self.session.execute(select(Template).order_by(Template.name)).scalars().all()
        )

    def upsert(
        self,
        *,
        name: str,
        channel: str,
        subject: Optional[str],
        body: str,
        updated_by: str,
    ) -> Template:
        existing = self.find_by_name(name)
        if existing is None:
            tpl = Template(
                name=name, channel=channel, subject=subject, body=body, updated_by=updated_by
            )
            self.session.add(tpl)
        else:
            existing.subject = subject
            existing.body = body
            existing.updated_by = updated_by
            tpl = existing
        self.session.flush()
        return tpl

    def delete(self, template: Template) -> None:
        self.session.delete(template)
        self.session.flush()
