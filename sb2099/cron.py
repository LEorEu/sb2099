"""周期任务：recount_cron（每分钟校正 live_hot 计数）+ archive_cron（每日清 raw_danmaku）。

由 web.app lifespan 在 startup 时拉起。设计文档 §7。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, text

from . import db as _db
from .models import RawDanmaku
from .settings import settings_cache

log = logging.getLogger(__name__)

__all__ = ["recount_loop", "archive_loop", "recount_once", "archive_once"]

_RECOUNT_INTERVAL_S = 60.0
_ARCHIVE_HOUR_LOCAL = 4  # 每日 04:00 本地时间
_ARCHIVE_CHECK_INTERVAL_S = 300.0  # 每 5 分钟检查一次是否到点


_RECOUNT_SQL = text(
    """
    WITH agg AS (
        SELECT
            content_norm,
            SUM(CASE WHEN ts >= :h24 THEN 1 ELSE 0 END) AS c24,
            SUM(CASE WHEN ts >= :d7  THEN 1 ELSE 0 END) AS c7d,
            COUNT(DISTINCT CASE WHEN ts >= :h24 THEN uid END) AS u24,
            COUNT(DISTINCT CASE WHEN ts >= :d7  THEN uid END) AS u7d
        FROM raw_danmaku
        WHERE ts >= :d7
        GROUP BY content_norm
    )
    UPDATE live_hot
    SET send_cnt_24h           = COALESCE((SELECT c24 FROM agg WHERE agg.content_norm = live_hot.content_norm), 0),
        send_cnt_7d            = COALESCE((SELECT c7d FROM agg WHERE agg.content_norm = live_hot.content_norm), 0),
        unique_sender_cnt_24h  = COALESCE((SELECT u24 FROM agg WHERE agg.content_norm = live_hot.content_norm), 0),
        unique_sender_cnt_7d   = COALESCE((SELECT u7d FROM agg WHERE agg.content_norm = live_hot.content_norm), 0)
    """
)


def _recount_sync() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    h24 = now - timedelta(hours=24)
    d7 = now - timedelta(days=7)
    with _db.SessionLocal() as session:
        session.execute(_RECOUNT_SQL, {"h24": h24, "d7": d7})
        session.commit()


async def recount_once() -> None:
    await asyncio.to_thread(_recount_sync)


async def recount_loop() -> None:
    while True:
        try:
            await recount_once()
        except Exception:
            log.exception("recount_cron failed")
        await asyncio.sleep(_RECOUNT_INTERVAL_S)


def _archive_sync() -> int:
    days = int(settings_cache.get("raw_retention_days", 30) or 30)
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    with _db.SessionLocal() as session:
        res = session.execute(delete(RawDanmaku).where(RawDanmaku.ts < cutoff))
        session.commit()
        return int(res.rowcount or 0)


async def archive_once() -> int:
    return await asyncio.to_thread(_archive_sync)


async def archive_loop() -> None:
    while True:
        now = datetime.now()  # local time
        target = now.replace(hour=_ARCHIVE_HOUR_LOCAL, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        # 切成 5min 块睡，便于 cancel 响应
        while wait > 0:
            chunk = min(_ARCHIVE_CHECK_INTERVAL_S, wait)
            await asyncio.sleep(chunk)
            wait -= chunk
        try:
            removed = await archive_once()
            log.info("archive_cron removed %d raw_danmaku rows", removed)
        except Exception:
            log.exception("archive_cron failed")
