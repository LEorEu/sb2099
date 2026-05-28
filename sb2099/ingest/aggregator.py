"""chat 事件聚合：raw_danmaku 入库 + live_noise_filters 过滤 + live_hot upsert。

不在此处更新 send_cnt_24h/7d/unique_sender_cnt_*：那由 cron.recount_cron 每分钟
重算（设计文档 §7 "增量 ++ + cron 校正"）。
"""
from __future__ import annotations

import asyncio
import logging
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .. import db as _db
from ..models import LiveHot, RawDanmaku
from ..normalize import normalize
from ..settings import settings_cache

log = logging.getLogger(__name__)

__all__ = ["persist_chat_event", "should_filter"]


def _normalized_filters() -> list[str]:
    raw = settings_cache.get("live_noise_filters", []) or []
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
    content_norm = normalize(content_raw)
    if not content_norm:
        return

    is_noise = should_filter(content_norm)

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

        existing = session.execute(
            select(LiveHot.id, LiveHot.send_cnt_total, LiveHot.is_filtered).where(
                LiveHot.content_norm == content_norm
            )
        ).first()

        if existing is None:
            session.execute(
                sqlite_insert(LiveHot).values(
                    content_norm=content_norm,
                    content_sample=content_raw,
                    first_seen=ts,
                    last_seen=ts,
                    send_cnt_total=1,
                    is_filtered=is_noise,
                )
            )
        else:
            session.execute(
                update(LiveHot)
                .where(LiveHot.id == existing.id)
                .values(
                    last_seen=ts,
                    send_cnt_total=existing.send_cnt_total + 1,
                    # 若新出现的 raw 不再命中规则但原行被标记，保持原状；规则改后由后台触发全量重扫
                    is_filtered=existing.is_filtered or is_noise,
                )
            )
        session.commit()


async def persist_chat_event(evt: dict) -> None:
    await asyncio.to_thread(_persist_sync, evt)
