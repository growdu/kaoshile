"""模板管理 API：列表 / 详情 / 更新 / 重置。"""
from __future__ import annotations

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.infra.db import get_db
from app.notification.templates import render as default_render
from app.repository.models import Template
from app.repository.template_repo import TemplateRepository

from app.api.manage import _require_admin

router = APIRouter()


# 默认模板的常量映射（reset 时用）
DEFAULT_TEMPLATES = {
    "EMAIL_TEMPLATE": ("email", default_render.EMAIL_TEMPLATE),
    "SMS_TEMPLATE": ("sms", default_render.SMS_TEMPLATE),
    "CONFIRM_EMAIL_TEMPLATE": ("email", default_render.CONFIRM_EMAIL_TEMPLATE),
    "CONFIRM_SMS_TEMPLATE": ("sms", default_render.CONFIRM_SMS_TEMPLATE),
}


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    channel: str
    subject: Optional[str]
    body: str
    updated_at: datetime
    updated_by: Optional[str]


class UpdateTemplateIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)
    subject: Optional[str] = Field(None, max_length=500)


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"ok": False, "error": {"code": code, "message": message}},
    )


@router.get("/api/manage/templates", tags=["manage", "templates"])
def list_templates(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    _require_admin(authorization)
    repo = TemplateRepository(db)
    items = [TemplateOut.model_validate(t).model_dump(mode="json") for t in repo.list()]
    return {"ok": True, "data": {"items": items}}


@router.get("/api/manage/templates/{name}", tags=["manage", "templates"])
def get_template(
    name: str,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    _require_admin(authorization)
    repo = TemplateRepository(db)
    tpl = repo.find_by_name(name)
    if tpl is None:
        # fallback 到默认
        if name in DEFAULT_TEMPLATES:
            channel, body = DEFAULT_TEMPLATES[name]
            return {
                "ok": True,
                "data": {
                    "name": name,
                    "channel": channel,
                    "subject": None,
                    "body": body,
                    "updated_at": None,
                    "updated_by": None,
                    "is_default": True,
                },
            }
        raise _err("template_not_found", f"template {name} not found", 404)
    return {"ok": True, "data": TemplateOut.model_validate(tpl).model_dump(mode="json")}


@router.put("/api/manage/templates/{name}", tags=["manage", "templates"])
def update_template(
    name: str,
    payload: UpdateTemplateIn,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    _require_admin(authorization)
    payload_admin = _require_admin(authorization)
    if name not in DEFAULT_TEMPLATES:
        raise _err("unknown_template", f"unknown template {name}", 400)
    channel, _ = DEFAULT_TEMPLATES[name]
    repo = TemplateRepository(db)
    tpl = repo.upsert(
        name=name,
        channel=channel,
        subject=payload.subject,
        body=payload.body,
        updated_by=payload_admin["username"],
    )
    return {"ok": True, "data": TemplateOut.model_validate(tpl).model_dump(mode="json")}


@router.delete("/api/manage/templates/{name}", tags=["manage", "templates"])
def reset_template(
    name: str,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> dict:
    """删除自定义覆盖，恢复为默认。"""
    _require_admin(authorization)
    if name not in DEFAULT_TEMPLATES:
        raise _err("unknown_template", f"unknown template {name}", 400)
    repo = TemplateRepository(db)
    tpl = repo.find_by_name(name)
    if tpl is not None:
        repo.delete(tpl)
    return {"ok": True, "data": {"message": f"template {name} reset to default"}}
