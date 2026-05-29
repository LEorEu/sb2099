"""投稿库搜索：FTS5 全文 + tag CSV 任一匹配 + sort 排序 + 仅 active 状态。

公开页 `/barrage` 与 `/api/barrage` 共用。LEFT JOIN user 拿投稿者昵称/头像，
**uid 不暴露给前端**（隐私最小化），只返回 submitter: null | {nickname, avatar}。
"""
from __future__ import annotations

from sqlalchemy import text

from . import db as _db
from .users import avatar_url

__all__ = ["search_barrage"]

_MAX_PAGE_SIZE = 100


def _iso(v: object) -> str | None:
    """SQLite raw text() returns datetime as string; ORM returns datetime obj."""
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()  # type: ignore[no-any-return]
    return str(v)


def search_barrage(
    q: str | None = None,
    tags: list[str] | None = None,
    sort: str = "new",
    page: int = 1,
    size: int = 20,
) -> dict:
    """返回 {list, total, last_page}。

    - `q`：FTS5 MATCH 查询；为空时跳过 FTS5 join
    - `tags`：CSV tag value 列表（如 `["00","02"]`），任一匹配 (OR) 即返回
    - `sort`：`"new"` (submit_time desc) 或 `"hot"` (cnt desc)
    - `page`：1-based；`size` 上限 100
    """
    page = max(1, int(page))
    size = max(1, min(_MAX_PAGE_SIZE, int(size)))
    offset = (page - 1) * size

    where: list[str] = ["b.status = 'active'"]
    params: dict[str, object] = {}
    join = ""

    if q:
        # trigram FTS5 仅在 query 长度 >= 3 时索引匹配；短 query fallback 到 LIKE 子串扫描
        if len(q) >= 3:
            join = "JOIN barrage_fts f ON f.rowid = b.id"
            where.append("barrage_fts MATCH :q")
            params["q"] = q
        else:
            where.append("b.content LIKE :q_like")
            params["q_like"] = f"%{q}%"

    if tags:
        tag_conds: list[str] = []
        for i, t in enumerate(tags):
            tag_conds.append(f"(',' || b.tags || ',') LIKE :tag{i}")
            params[f"tag{i}"] = f"%,{t},%"
        where.append("(" + " OR ".join(tag_conds) + ")")

    where_sql = " AND ".join(where)
    order_sql = "b.cnt DESC, b.id DESC" if sort == "hot" else "b.submit_time DESC, b.id DESC"

    list_sql = text(
        f"""
        SELECT b.id, b.content, b.tags, b.cnt, b.submit_time, b.status,
               u.nickname AS submitter_nickname, u.avatar AS submitter_avatar
        FROM barrage b {join}
        LEFT JOIN user u ON u.uid = b.submitter_uid
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT :limit OFFSET :offset
        """
    )
    count_sql = text(
        f"""
        SELECT COUNT(*) FROM barrage b {join}
        WHERE {where_sql}
        """
    )

    with _db.SessionLocal() as s:
        total = s.execute(count_sql, params).scalar_one()
        rows = s.execute(
            list_sql,
            {**params, "limit": size, "offset": offset},
        ).mappings().all()

    items = [
        {
            "id": r["id"],
            "content": r["content"],
            "tags": r["tags"],
            "cnt": r["cnt"],
            "submit_time": _iso(r["submit_time"]),
            "submitter": (
                {
                    "nickname": r["submitter_nickname"],
                    "avatar": avatar_url(r["submitter_avatar"]),
                }
                if r["submitter_nickname"]
                else None
            ),
        }
        for r in rows
    ]
    return {
        "list": items,
        "total": int(total),
        "last_page": offset + len(items) >= int(total),
    }
