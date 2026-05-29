"""Tag 投票辅助：阈值读取、票数统计（按 voter 去重）、达阈值结算到 barrage.tags。

`vote_count` 用 SQL 表达式按 `voter_uid` 优先 / `voter_ip_hash` 兜底去重，
即同一个登录用户算 1 票、同一个匿名 IP 算 1 票，二者并存按各自计。
`settle_tag` 把达阈值的 tag append 到 `barrage.tags`（无重复、不动其他 tag）。
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Barrage
from .settings import settings_cache

__all__ = [
    "vote_threshold",
    "vote_count",
    "settle_tag",
    "settle_all_for_tag",
]


def vote_threshold() -> int:
    try:
        return max(1, int(settings_cache.get("tag_vote_threshold", 3) or 3))
    except (TypeError, ValueError):
        return 3


def vote_count(session: Session, barrage_id: int, tag_value: str) -> int:
    """SQLite: 同 (barrage_id, tag_value) 下按 COALESCE('u:'||uid, 'i:'||ip_hash) 去重。"""
    return int(
        session.execute(
            text(
                "SELECT COUNT(*) FROM ("
                "  SELECT COALESCE('u:'||voter_uid, 'i:'||voter_ip_hash) AS k "
                "  FROM barrage_tag_vote "
                "  WHERE barrage_id = :b AND tag_value = :t "
                "  GROUP BY k"
                ") AS u"
            ),
            {"b": barrage_id, "t": tag_value},
        ).scalar()
        or 0
    )


def settle_tag(session: Session, barrage_id: int, tag_value: str) -> bool:
    """若该 (barrage_id, tag) 票数 >= 阈值且 tag 不在 barrage.tags，append 之；返回是否新加。

    调用方负责确保 tag 已 enabled。session 由调用方 commit。
    """
    count = vote_count(session, barrage_id, tag_value)
    if count < vote_threshold():
        return False
    row = session.get(Barrage, barrage_id)
    if row is None:
        return False
    current = {t for t in (row.tags or "").split(",") if t}
    if tag_value in current:
        return False
    current.add(tag_value)
    row.tags = ",".join(sorted(current))
    return True


def settle_all_for_tag(session: Session, tag_value: str) -> int:
    """tag 被 admin 批准时回溯：对所有给过该 tag 投票的 barrage 重新结算。

    返回本次实际新增 tag 的 barrage 行数。session 由调用方 commit。
    """
    barrage_ids = [
        bid
        for (bid,) in session.execute(
            text("SELECT DISTINCT barrage_id FROM barrage_tag_vote WHERE tag_value=:t"),
            {"t": tag_value},
        ).all()
    ]
    added = 0
    for bid in barrage_ids:
        if settle_tag(session, bid, tag_value):
            added += 1
    return added
