"""用户账户 API：注册 / 登录 / 我的订阅 / 找回密码 / 重置。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.infra.db import get_db
from app.repository.subscription_repo import SubscriptionRepository
from app.repository.user_repo import UserRepository
from app.repository.schemas import MySubscriptionsOut, SubscriptionOut
from app.usecase.account import AccountError, AccountService
from app.usecase.notification import NotificationService

router = APIRouter()


def _err(code: str, message: str, status: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"ok": False, "error": {"code": code, "message": message}},
    )


class RegisterIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)


class LoginIn(BaseModel):
    email: str
    password: str


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    token: str
    new_password: str = Field(..., min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    phone: Optional[str] = None


class UpdateMeIn(BaseModel):
    phone: Optional[str] = Field(None, max_length=20)
    current_password: Optional[str] = Field(None, min_length=1, max_length=200)
    new_password: Optional[str] = Field(None, min_length=1, max_length=200)


class ChangeEmailIn(BaseModel):
    new_email: str = Field(..., min_length=3, max_length=200)
    current_password: str = Field(..., min_length=1, max_length=200)


class ChangeEmailOut(BaseModel):
    message: str
    dev_token: Optional[str] = None


def _service(db: Session) -> AccountService:
    notifier = NotificationService(log_repo=None)  # 只走一次性通道
    return AccountService(
        UserRepository(db),
        SubscriptionRepository(db),
        notifier=notifier,
    )


@router.post("/api/account/register", tags=["account"])
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> dict:
    svc = _service(db)
    try:
        user = svc.register(email=payload.email, password=payload.password, phone=payload.phone)
    except AccountError as e:
        raise _err(e.code, e.message, 400)
    return {
        "ok": True,
        "data": UserOut(id=user.id, email=user.email).model_dump(),
    }


@router.post("/api/account/login", tags=["account"])
def login(payload: LoginIn, db: Session = Depends(get_db)) -> dict:
    svc = _service(db)
    try:
        token = svc.login(email=payload.email, password=payload.password)
    except AccountError as e:
        raise _err(e.code, e.message, 401)
    return {"ok": True, "data": {"token": token, "expires_in_days": 1}}


@router.patch("/api/account/me", tags=["account"])
def update_me(
    payload: UpdateMeIn,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    """自助更新：phone / password（改密码需 current_password）。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise _err("unauthorized", "missing bearer token", 401)
    token = authorization.split(" ", 1)[1]
    try:
        auth = AccountService.require_user(token)
    except AccountError as e:
        raise _err(e.code, e.message, 401)
    svc = _service(db)
    try:
        user = svc.update_profile(
            auth["user_id"],
            phone=payload.phone,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except AccountError as e:
        raise _err(e.code, e.message, 400)
    return {
        "ok": True,
        "data": UserOut(id=user.id, email=user.email, phone=user.phone).model_dump(),
    }


@router.post("/api/account/change-email", tags=["account"])
def change_email(
    payload: ChangeEmailIn,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    """发起邮箱迁移（需校验旧密码）。

    dev_token 字段仅开发环境返回；生产只通过邮件发送。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise _err("unauthorized", "missing bearer token", 401)
    token = authorization.split(" ", 1)[1]
    try:
        auth = AccountService.require_user(token)
    except AccountError as e:
        raise _err(e.code, e.message, 401)
    svc = _service(db)
    try:
        dev_token = svc.change_email(
            auth["user_id"],
            payload.new_email,
            payload.current_password,
        )
    except AccountError as e:
        raise _err(e.code, e.message, 400)
    return {
        "ok": True,
        "data": ChangeEmailOut(
            message="确认链接已发送到新邮箱",
            dev_token=dev_token,
        ).model_dump(),
    }


@router.get("/api/account/change-email/verify", tags=["account"])
def verify_change_email(
    token: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    """点击邮件中的确认链接 → 完成邮箱迁移。"""
    svc = _service(db)
    try:
        user = svc.confirm_change_email(token)
    except AccountError as e:
        raise _err(e.code, e.message, 400)
    return {
        "ok": True,
        "data": UserOut(id=user.id, email=user.email, phone=user.phone).model_dump(),
    }


@router.get("/api/account/me/subscriptions", tags=["account"])
def my_subscriptions(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise _err("unauthorized", "missing bearer token", 401)
    token = authorization.split(" ", 1)[1]
    try:
        payload = AccountService.require_user(token)
    except AccountError as e:
        raise _err(e.code, e.message, 401)
    email = payload["email"]
    sub_repo = SubscriptionRepository(db)
    items = [SubscriptionOut.model_validate(s) for s in sub_repo.find_by_email(email)]
    return {
        "ok": True,
        "data": {"items": [i.model_dump(mode="json") for i in items]},
    }


@router.post("/api/account/forgot-password", tags=["account"])
def forgot_password(payload: ForgotIn, db: Session = Depends(get_db)) -> dict:
    """签发 reset token 并尝试发送邮件。

    不论用户是否存在都返回 ok=true（不泄露存在性）。
    """
    svc = _service(db)
    token = svc.forgot_password(payload.email)
    return {
        "ok": True,
        "data": {
            "message": "如果邮箱存在，重置链接已发出",
            # 仅 dev 模式返回 token，生产不返回
            "dev_token": token,
        },
    }


@router.post("/api/account/reset-password", tags=["account"])
def reset_password(payload: ResetIn, db: Session = Depends(get_db)) -> dict:
    svc = _service(db)
    try:
        svc.reset_password(payload.token, payload.new_password)
    except AccountError as e:
        raise _err(e.code, e.message, 400)
    return {"ok": True, "data": {"message": "密码已重置"}}
