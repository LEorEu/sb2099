"""周期任务：recount_cron（每分钟从当前数据日 raw 重建 daily_hot）+ archive_cron（每日清过期 raw 与 daily_hot）。

由 web.app lifespan 在 startup 时拉起。设计文档 §7。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, text

from . import db as _db
from .ingest.aggregator import should_filter
from .live_day import current_live_window
from .models import RawDanmaku
from .settings import settings_cache

log = logging.getLogger(__name__)

__all__ = ["recount_loop", "archive_loop", "recount_once", "archive_once"]

_RECOUNT_INTERVAL_S = 60.0
_ARCHIVE_HOUR_LOCAL = 4  # 每日 04:00 本地时间
_ARCHIVE_CHECK_INTERVAL_S = 300.0  # 每 5 分钟检查一次是否到点


def _recount_sync() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    live_date, day_start = current_live_window(now)
    live_date_str = live_date.isoformat()
    threshold = int(settings_cache.get("live_hot_min_unique_senders_24h", 20) or 0)

    with _db.SessionLocal() as session:
        rows = session.execute(
            text(
                "SELECT content_norm, content_raw AS sample, "
                "COUNT(*) AS send_cnt, COUNT(DISTINCT uid) AS uniq, "
                "MIN(ts) AS first_seen, MAX(ts) AS last_seen "
                "FROM raw_danmaku WHERE ts >= :start "
                "GROUP BY content_norm HAVING COUNT(DISTINCT uid) >= :thr"
            ),
            {"start": day_start, "thr": threshold},
        ).mappings().all()

        qualifiers = [r for r in rows if not should_filter(r["content_norm"])]
        keep = {r["content_norm"] for r in qualifiers}

        existing = session.execute(
            text("SELECT content_norm FROM daily_hot WHERE live_date = :d"),
            {"d": live_date_str},
        ).scalars().all()
        for cn in existing:
            if cn not in keep:
                session.execute(
                    text("DELETE FROM daily_hot WHERE live_date=:d AND content_norm=:cn"),
                    {"d": live_date_str, "cn": cn},
                )

        for r in qualifiers:
            session.execute(
                text(
                    "INSERT INTO daily_hot(live_date, content_norm, content_sample, "
                    "send_cnt, unique_sender_cnt, first_seen, last_seen, page_copy_cnt, is_filtered) "
                    "VALUES (:d, :cn, :s, :sc, :u, :fs, :ls, 0, 0) "
                    "ON CONFLICT(live_date, content_norm) DO UPDATE SET "
                    "content_sample=excluded.content_sample, send_cnt=excluded.send_cnt, "
                    "unique_sender_cnt=excluded.unique_sender_cnt, "
                    "first_seen=excluded.first_seen, last_seen=excluded.last_seen"
                ),
                {
                    "d": live_date_str,
                    "cn": r["content_norm"],
                    "s": r["sample"],
                    "sc": r["send_cnt"],
                    "u": r["uniq"],
                    "fs": r["first_seen"],
                    "ls": r["last_seen"],
                },
            )
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
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    raw_days = int(settings_cache.get("raw_retention_days", 2) or 2)
    raw_cutoff = now - timedelta(days=raw_days)

    hot_days = int(settings_cache.get("daily_hot_retention_days", 7) or 7)
    live_date, _ = current_live_window(now)
    hot_cutoff = (live_date - timedelta(days=hot_days)).isoformat()

    with _db.SessionLocal() as session:
        res = session.execute(delete(RawDanmaku).where(RawDanmaku.ts < raw_cutoff))
        session.execute(
            text("DELETE FROM daily_hot WHERE live_date < :c"), {"c": hot_cutoff}
        )
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
