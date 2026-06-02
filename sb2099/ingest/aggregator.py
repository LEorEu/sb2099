"""chat 事件聚合：把 chat 事件写入 raw_danmaku，并维护 user 名册。

热词聚合（daily_hot upsert）移至 recount_cron，不再在此处进行。
"""
from __future__ import annotations

import asyncio
import logging
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import case
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .. import db as _db
from ..models import RawDanmaku, User
from ..normalize import normalize
from ..settings import settings_cache

log = logging.getLogger(__name__)

__all__ = [
    "persist_chat_event",
    "persist_user_from_chat",
    "should_filter",
    "normalized_suffix_strips",
    "normalized_cut_markers",
]


def _normalized_filters() -> list[str]:
    raw = settings_cache.get("live_noise_filters", []) or []
    out: list[str] = []
    for kw in raw:
        n = normalize(kw)
        if n:
            out.append(n)
    return out


def normalized_suffix_strips() -> list[str]:
    """从 setting 读 live_suffix_strips,规范化每条尾缀词,按长度降序返回。

    供 ingest 入库与后台 recompute 计算 content_norm 时传给 normalize(),
    使带 douyuex 自定义尾缀的复制弹幕聚合为同一条。长度降序保证先剥较长尾缀。
    """
    raw = settings_cache.get("live_suffix_strips", []) or []
    out: list[str] = []
    for kw in raw:
        n = normalize(kw)
        if n:
            out.append(n)
    out.sort(key=len, reverse=True)
    return out


def normalized_cut_markers() -> list[str]:
    """从 setting 读 live_cut_markers,规范化每条标记词。

    供 ingest 入库与后台 recompute 计算 content_norm 时传给 normalize(cut_markers=...),
    把 douyuex 那种「固定前缀 + 任意装饰」的整条尾巴从标记处截掉。
    """
    raw = settings_cache.get("live_cut_markers", []) or []
    out: list[str] = []
    for kw in raw:
        n = normalize(kw)
        if n:
            out.append(n)
    return out


def _noise_match(content_norm: str, filters: list[str]) -> bool:
    """整句精确匹配:content_norm 完全等于任一(规范化后的)关键词。"""
    return content_norm in filters


def _is_decorated_noise(content_norm: str, filters: list[str]) -> bool:
    """noise 关键词的"装饰/重复"变体:
    - 至少包含一个 noise 关键词作为子串
    - 把所有 noise 关键词字符剥掉后,剩余字符不再有任何字母(汉字/英文等)
    例如:晚安晚安晚安、晚安!!!、晚安~晚安~ → 命中。晚安宝贝 → 不命中(剥后"宝贝"含字母)。
    """
    if not filters:
        return False
    if not any(kw in content_norm for kw in filters):
        return False
    stripped = content_norm
    for kw in filters:
        stripped = stripped.replace(kw, "")
    for ch in stripped:
        if unicodedata.category(ch).startswith("L"):
            return False
    return True


def _is_low_quality(content_norm: str, min_length: int, max_length: int) -> bool:
    """太短 / 太长 / 不含任一字母(汉字、英文、日文等)的内容,标 is_filtered。"""
    if len(content_norm) < min_length:
        return True
    if max_length > 0 and len(content_norm) > max_length:
        return True
    for ch in content_norm:
        if unicodedata.category(ch).startswith("L"):
            return False
    return True


def should_filter(content_norm: str) -> bool:
    """聚合所有"应当标 is_filtered=1"的判断。供 rescan 复用。"""
    min_length = int(settings_cache.get("live_hot_min_length", 2) or 2)
    max_length = int(settings_cache.get("live_hot_max_length", 80) or 0)
    if _is_low_quality(content_norm, min_length, max_length):
        return True
    filters = _normalized_filters()
    if _noise_match(content_norm, filters):
        return True
    if _is_decorated_noise(content_norm, filters):
        return True
    return False


def _persist_sync(evt: dict) -> None:
    ts_ms = evt.get("ts")
    if not isinstance(ts_ms, (int, float)):
        return
    ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
    content_raw = evt.get("content") or ""
    if not content_raw:
        return
    content_norm = normalize(
        content_raw,
        suffixes=normalized_suffix_strips(),
        cut_markers=normalized_cut_markers(),
    )
    if not content_norm:
        return

    with _db.SessionLocal() as session:
        session.execute(
            sqlite_insert(RawDanmaku).values(
                ts=ts,
                uid=evt.get("uid"),
                nickname=evt.get("nickname"),
                content_raw=content_raw,
                content_norm=content_norm,
            )
        )
        session.commit()


async def persist_chat_event(evt: dict) -> None:
    await asyncio.to_thread(_persist_sync, evt)


def _persist_user_sync(evt: dict) -> None:
    """chat 事件 → upsert user 表。空值不覆盖已有数据。"""
    uid = evt.get("uid")
    if not uid:
        return
    ts_ms = evt.get("ts")
    if not isinstance(ts_ms, (int, float)):
        return
    now = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
    nickname = evt.get("nickname")
    avatar = evt.get("ic")

    stmt = sqlite_insert(User).values(
        uid=uid,
        nickname=nickname,
        avatar=avatar,
        first_seen=now,
        last_seen=now,
        source="live",
    )
    excluded = stmt.excluded
    # 已存在时：非空字段才覆盖；source 不动（保留 seed 的就是 seed）
    stmt = stmt.on_conflict_do_update(
        index_elements=["uid"],
        set_={
            "nickname": case(
                (excluded.nickname.is_not(None), excluded.nickname),
                else_=User.nickname,
            ),
            "avatar": case(
                (excluded.avatar.is_not(None), excluded.avatar),
                else_=User.avatar,
            ),
            "last_seen": excluded.last_seen,
        },
    )
    with _db.SessionLocal() as session:
        session.execute(stmt)
        session.commit()


async def persist_user_from_chat(evt: dict) -> None:
    await asyncio.to_thread(_persist_user_sync, evt)
