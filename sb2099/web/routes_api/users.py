"""GET /api/users/search —— 投稿署名用的昵称/uid 模糊搜索。"""
from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import select

from ... import db as _db
from ...models import User
from ...ratelimit import limiter, rate_for

router = APIRouter(prefix="/api")


@router.get("/users/search")
@limiter.limit(lambda: rate_for("ratelimit_copy_per_hour_per_ip", 200))
def search_users(request: Request, q: str = "", limit: int = 10) -> dict:
    """昵称模糊搜索；q 全数字时按 uid 前缀。

    返回上限 10 条，按 last_seen 倒序。**只返 nickname + avatar，不返 uid**——
    avatar 是斗鱼 CDN 完整 URL；前端获取 uid 走另一路（投稿请求里带 uid 时由该端点
    返回的列表项自己附带，下面 results 里仍含 uid 字段供前端选中后回传，但不公开列举）。

    要求 q > 2 字符；空 / 单双字 q 一律返回空列表，避免被批量拉名册。
    """
    from ...users import avatar_url

    q = (q or "").strip()
    if len(q) <= 2:
        return {"results": []}
    limit = max(1, min(int(limit or 10), 10))

    with _db.SessionLocal() as s:
        if q.isdigit():
            stmt = (
                select(User.uid, User.nickname, User.avatar)
                .where(User.uid.like(f"{q}%"))
                .order_by(User.last_seen.desc())
                .limit(limit)
            )
        else:
            stmt = (
                select(User.uid, User.nickname, User.avatar)
                .where(User.nickname.like(f"%{q}%"))
                .order_by(User.last_seen.desc())
                .limit(limit)
            )
        rows = s.execute(stmt).all()

    return {
        "results": [
            {"uid": r.uid, "nickname": r.nickname, "avatar": avatar_url(r.avatar)}
            for r in rows
        ]
    }
