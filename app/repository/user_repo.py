"""User 数据访问层。"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repository.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: str) -> Optional[User]:
        return self.session.get(User, user_id)

    def find_by_email(self, email: str) -> Optional[User]:
        return self.session.execute(
            select(User).where(User.email == email.lower())
        ).scalar_one_or_none()

    def insert(
        self, *, email: str, password_hash: str, phone: Optional[str] = None
    ) -> User:
        user = User(
            id=str(uuid.uuid4()),
            email=email.lower(),
            password_hash=password_hash,
            phone=phone,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def set_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        self.session.flush()
