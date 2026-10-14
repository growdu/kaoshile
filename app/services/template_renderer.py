"""模板渲染器：DB 优先 + 默认 fallback。

约定：
- TemplateRenderer.render(template_name, ctx) 从 DB 取模板，缺失则用默认；
- 默认模板保留在 app/notification/templates/render.py；
- 调用方无需关心 DB 与 fallback 切换。
"""
from __future__ import annotations

from typing import Mapping

from sqlalchemy.orm import Session

from app.notification.templates import render as default_render
from app.repository.template_repo import TemplateRepository


class TemplateRenderer:
    """DB 优先的模板渲染器。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = TemplateRepository(session)

    def render(
        self,
        *,
        template_name: str,
        ctx: Mapping[str, object],
    ) -> str:
        """渲染模板。优先用 DB；不存在则尝试默认。"""
        tpl = self.repo.find_by_name(template_name)
        if tpl is not None:
            return default_render.render(tpl.body, ctx)
        # fallback：默认模板常量名
        template_text = getattr(default_render, template_name, None)
        if isinstance(template_text, str):
            return default_render.render(template_text, ctx)
        raise KeyError(f"template {template_name!r} not found")
