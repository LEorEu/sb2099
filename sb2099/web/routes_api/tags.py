"""GET /api/tags —— 开放标签词表（仅 enabled）。"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from ... import db as _db
from ...models import Tag

router = APIRouter(prefix="/api")


@router.get("/tags")
def list_tags() -> dict:
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(Tag.value, Tag.label, Tag.icon_url, Tag.sort)
            .where(Tag.enabled.is_(True))
            .order_by(Tag.sort)
        ).all()
    return {
        "data": [
            {"value": r.value, "label": r.label, "icon_url": r.icon_url, "sort": r.sort}
            for r in rows
        ]
    }
