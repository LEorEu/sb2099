"""数据日（live_date）边界纯函数：CST(UTC+8) 04:00 → 次日 04:00。

ingest/cron/web 统一从这里取「当前数据日」与「某弹幕归属数据日」，禁止各处自行
拼时区/小时。所有入参为 UTC naive（与库内 ts 一致）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
_LIVE_DAY_START_HOUR = 4

__all__ = ["current_live_window", "live_date_of", "CST"]


def current_live_window(now_utc_naive: datetime) -> tuple[date, datetime]:
    """返回 (当前数据日, 该数据日起点的 UTC naive 时刻)。"""
    now_cst = now_utc_naive.replace(tzinfo=timezone.utc).astimezone(CST)
    start_cst = now_cst.replace(hour=_LIVE_DAY_START_HOUR, minute=0, second=0, microsecond=0)
    if now_cst < start_cst:
        start_cst -= timedelta(days=1)
    live_date = start_cst.date()
    start_utc = start_cst.astimezone(timezone.utc).replace(tzinfo=None)
    return live_date, start_utc


def live_date_of(ts_utc_naive: datetime) -> date:
    """某条弹幕（UTC naive）归属的数据日。"""
    ts_cst = ts_utc_naive.replace(tzinfo=timezone.utc).astimezone(CST)
    return (ts_cst - timedelta(hours=_LIVE_DAY_START_HOUR)).date()
