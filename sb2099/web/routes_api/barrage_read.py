"""GET 投稿库只读视图：搜索 / 按 id 批量取 / 随机一条。"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from ... import db as _db
from ...models import Barrage, User
from ...search import search_barrage

router = APIRouter(prefix="/api")


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


@router.get("/barrage/by-ids")
def get_barrages_by_ids(ids: str = Query("", description="CSV barrage ids，最多 200")) -> dict:
    """按 id 批量取 active 投稿正文，供收藏夹展示。保持请求顺序，丢弃失效 id。"""
    from ...users import avatar_url

    id_list: list[int] = []
    seen: set[int] = set()
    for part in ids.split(","):
        part = part.strip()
        if part.isdigit():
            n = int(part)
            if n not in seen:
                seen.add(n)
                id_list.append(n)
    id_list = id_list[:200]
    if not id_list:
        return {"data": []}
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(
                Barrage.id, Barrage.content, Barrage.tags, Barrage.cnt, Barrage.submit_time,
                User.nickname.label("submitter_nickname"),
                User.avatar.label("submitter_avatar"),
            )
            .outerjoin(User, User.uid == Barrage.submitter_uid)
            .where(Barrage.id.in_(id_list), Barrage.status == "active")
        ).all()
    by_id: dict[int, dict] = {}
    for r in rows:
        submitter = (
            {"nickname": r.submitter_nickname, "avatar": avatar_url(r.submitter_avatar)}
            if r.submitter_nickname
            else None
        )
        by_id[r.id] = {
            "id": r.id,
            "content": r.content,
            "tags": r.tags,
            "cnt": r.cnt,
            "submit_time": r.submit_time.isoformat() if r.submit_time else None,
            "submitter": submitter,
        }
    return {"data": [by_id[i] for i in id_list if i in by_id]}


@router.get("/random")
def get_random() -> dict:
    from ...users import avatar_url

    with _db.SessionLocal() as s:
        row = s.execute(
            select(
                Barrage.id,
                Barrage.content,
                Barrage.tags,
                Barrage.cnt,
                Barrage.submit_time,
                User.nickname.label("submitter_nickname"),
                User.avatar.label("submitter_avatar"),
            )
            .outerjoin(User, User.uid == Barrage.submitter_uid)
            .where(Barrage.status == "active")
            .order_by(func.random())
            .limit(1)
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="empty barrage library")
    submitter = None
    if row.submitter_nickname:
        submitter = {
            "nickname": row.submitter_nickname,
            "avatar": avatar_url(row.submitter_avatar),
        }
    return {
        "data": {
            "id": row.id,
            "content": row.content,
            "tags": row.tags,
            "cnt": row.cnt,
            "submit_time": row.submit_time.isoformat() if row.submit_time else None,
            "submitter": submitter,
        }
    }
