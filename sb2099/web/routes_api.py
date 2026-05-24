"""/api/* JSON 路由 — 切片 R（只读）。POST 路由留给下一轮 W。"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select, text

from .. import __version__ as sb_version
from .. import db as _db
from ..models import Barrage, Tag
from ..search import search_barrage

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


_LIVE_WINDOWS = {
    "day": ("send_cnt_24h", "unique_sender_cnt_24h", 10),
    "week": ("send_cnt_7d", "unique_sender_cnt_7d", 50),
}


@router.get("/live")
def get_live(window: Literal["day", "week"] = "day") -> dict:
    cnt_col, uniq_col, limit = _LIVE_WINDOWS[window]
    sql = text(
        f"SELECT id, content_sample, {cnt_col} AS send_cnt, {uniq_col} AS unique_senders, "
        "last_seen FROM live_hot WHERE is_filtered=0 "
        f"ORDER BY {cnt_col} DESC, last_seen DESC LIMIT :limit"
    )
    with _db.SessionLocal() as s:
        rows = s.execute(sql, {"limit": limit}).mappings().all()
    return {
        "window": window,
        "data": [
            {
                "id": r["id"],
                "content_sample": r["content_sample"],
                "send_cnt": int(r["send_cnt"] or 0),
                "unique_senders": int(r["unique_senders"] or 0),
                "last_seen": (
                    r["last_seen"].isoformat()
                    if hasattr(r["last_seen"], "isoformat") else (str(r["last_seen"]) if r["last_seen"] else None)
                ),
            }
            for r in rows
        ],
    }


@router.get("/barrage")
def get_barrage(
    q: str | None = None,
    tag: str | None = Query(None, description="CSV: 00,02"),
    sort: Literal["new", "hot"] = "new",
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    tags = [t for t in tag.split(",") if t] if tag else None
    return {"data": search_barrage(q=q, tags=tags, sort=sort, page=page, size=size)}


@router.get("/random")
def get_random() -> dict:
    with _db.SessionLocal() as s:
        row = s.execute(
            select(Barrage.id, Barrage.content, Barrage.tags, Barrage.cnt, Barrage.submit_time)
            .where(Barrage.status == "active")
            .order_by(func.random())
            .limit(1)
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="empty barrage library")
    return {
        "data": {
            "id": row.id,
            "content": row.content,
            "tags": row.tags,
            "cnt": row.cnt,
            "submit_time": row.submit_time.isoformat() if row.submit_time else None,
        }
    }


@router.get("/userscript/version")
def get_userscript_version() -> dict:
    return {"version": sb_version}
