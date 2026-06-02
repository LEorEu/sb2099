"""GET /api/live —— 直播现场热榜（今日 24h / 近 7 天，底层 daily_hot）。"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from sqlalchemy import text

from ... import db as _db

router = APIRouter(prefix="/api")


def _live_rows(window: str):
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if window == "day":
        # 滚动 24 小时窗口（按 last_seen），跨越凌晨 4 点数据日切分仍能看到昨晚的榜。
        # 同一内容若横跨两个数据日，按 content_norm 聚合求和。
        cutoff = now - timedelta(hours=24)
        sql = text(
            "SELECT t.*, b.id AS barrage_id, b.tags AS barrage_tags FROM ("
            "  SELECT d.content_norm AS content_norm, "
            "    (SELECT d2.id FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "       AND d2.last_seen>=:cut AND d2.is_filtered=0 ORDER BY d2.last_seen DESC LIMIT 1) AS id, "
            "    (SELECT d2.content_sample FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "       AND d2.last_seen>=:cut AND d2.is_filtered=0 ORDER BY d2.last_seen DESC LIMIT 1) AS content_sample, "
            "    SUM(d.send_cnt) AS send_cnt, MAX(d.unique_sender_cnt) AS unique_senders, "
            "    MAX(d.last_seen) AS last_seen "
            "  FROM daily_hot d WHERE d.last_seen >= :cut AND d.is_filtered = 0 "
            "  GROUP BY d.content_norm "
            "  ORDER BY send_cnt DESC, last_seen DESC LIMIT 10"
            ") t LEFT JOIN barrage b ON b.content_norm = t.content_norm AND b.status='active'"
        )
        params = {"cut": cutoff}
    else:
        from ...live_day import current_live_window
        live_date, _ = current_live_window(now)
        wk_start = (live_date - timedelta(days=6)).isoformat()
        sql = text(
            "SELECT t.*, b.id AS barrage_id, b.tags AS barrage_tags FROM ("
            "  SELECT d.content_norm AS content_norm, "
            "    (SELECT d2.id FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "       AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS id, "
            "    (SELECT d2.content_sample FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "       AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS content_sample, "
            "    SUM(d.send_cnt) AS send_cnt, MAX(d.unique_sender_cnt) AS unique_senders, "
            "    MAX(d.last_seen) AS last_seen "
            "  FROM daily_hot d WHERE d.live_date >= :wk AND d.is_filtered = 0 "
            "  GROUP BY d.content_norm "
            "  ORDER BY send_cnt DESC, last_seen DESC LIMIT 50"
            ") t LEFT JOIN barrage b ON b.content_norm = t.content_norm AND b.status='active'"
        )
        params = {"wk": wk_start}
    with _db.SessionLocal() as s:
        return s.execute(sql, params).mappings().all()


def _first_senders(norms: list[str]) -> dict[str, dict]:
    """每条 content_norm 的「首个发送者」（最早 ts 的 raw_danmaku）→ {nickname, avatar}。

    nickname 取自 raw_danmaku（去规范化前的实时昵称），avatar 回 user 名册。
    raw 已被留存策略清理的内容，取到的就是「现存最早」一条；无昵称则不返回。
    """
    from sqlalchemy import bindparam
    from ...users import avatar_url

    norms = [n for n in norms if n]
    if not norms:
        return {}
    sql = text(
        "SELECT rd.content_norm AS cn, rd.nickname AS nickname, u.avatar AS avatar "
        "FROM raw_danmaku rd "
        "JOIN (SELECT content_norm, MIN(ts) AS mts FROM raw_danmaku "
        "      WHERE content_norm IN :norms GROUP BY content_norm) m "
        "  ON m.content_norm = rd.content_norm AND m.mts = rd.ts "
        "LEFT JOIN user u ON u.uid = rd.uid"
    ).bindparams(bindparam("norms", expanding=True))
    out: dict[str, dict] = {}
    with _db.SessionLocal() as s:
        for r in s.execute(sql, {"norms": norms}).mappings().all():
            cn = r["cn"]
            if cn in out or not r["nickname"]:
                continue
            out[cn] = {"nickname": r["nickname"], "avatar": avatar_url(r["avatar"])}
    return out


@router.get("/live")
def get_live(window: Literal["day", "week"] = "day") -> dict:
    from ...normalize import strip_decorations
    from ...ingest.aggregator import normalized_suffix_strips, normalized_cut_markers

    rows = _live_rows(window)
    first_by_norm = _first_senders([r["content_norm"] for r in rows])
    _suf = normalized_suffix_strips()
    _cm = normalized_cut_markers()
    return {
        "window": window,
        "data": [
            {
                "id": r["id"],
                "content_sample": strip_decorations(r["content_sample"], _suf, _cm),
                "send_cnt": int(r["send_cnt"] or 0),
                "unique_senders": int(r["unique_senders"] or 0),
                "last_seen": (
                    r["last_seen"].isoformat()
                    if hasattr(r["last_seen"], "isoformat")
                    else (str(r["last_seen"]) if r["last_seen"] else None)
                ),
                "in_library": r["barrage_id"] is not None,
                "barrage_tags": r["barrage_tags"],
                "first_sender": first_by_norm.get(r["content_norm"]),
            }
            for r in rows
        ],
    }
