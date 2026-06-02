"""routes_api 子模块共用的小工具。"""
from __future__ import annotations

from sqlalchemy import select

from ...models import User

__all__ = ["resolve_submitter_uid"]


def resolve_submitter_uid(session, uid: str | None) -> str | None:
    """uid 必须在 user 表里才视为有效；否则当匿名处理（不报错）。"""
    if not uid:
        return None
    return session.execute(select(User.uid).where(User.uid == uid)).scalar_one_or_none()
