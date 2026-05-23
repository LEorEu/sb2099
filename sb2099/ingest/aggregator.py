"""极简聚合：chat 事件 → raw_danmaku 入库。live_hot 聚合留 TODO。

后续要加：
- §2.5 live_noise_filters 子串过滤（命中即跳过 live_hot 聚合，但 raw_danmaku 仍落库）
- live_hot upsert（按 content_norm 合并）
- send_cnt_24h/7d 增量统计
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import insert

from ..db import SessionLocal
from ..models import RawDanmaku
from ..normalize import normalize

log = logging.getLogger(__name__)

__all__ = ["persist_chat_event"]


def _persist_sync(evt: dict) -> None:
    ts_ms = evt.get("ts")
    if not isinstance(ts_ms, (int, float)):
        return
    ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
    content_raw = evt.get("content") or ""
    if not content_raw:
        return
    row = {
        "ts": ts,
        "uid": evt.get("uid"),
        "nickname": evt.get("nickname"),
        "content_raw": content_raw,
        "content_norm": normalize(content_raw),
    }
    with SessionLocal() as session:
        session.execute(insert(RawDanmaku).values(**row))
        session.commit()


async def persist_chat_event(evt: dict) -> None:
    await asyncio.to_thread(_persist_sync, evt)
