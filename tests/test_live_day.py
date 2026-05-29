"""数据日边界（CST 04:00）纯函数测试。"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sb2099.live_day import current_live_window, live_date_of

CST = timezone(timedelta(hours=8))


def _utc_naive(y, mo, d, h, mi, tz=CST):
    """构造某时区本地时刻对应的 UTC naive。"""
    return datetime(y, mo, d, h, mi, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)


def test_live_date_of_before_4am_is_previous_day():
    # CST 2026-05-29 03:59 → 属于数据日 2026-05-28
    ts = _utc_naive(2026, 5, 29, 3, 59)
    assert live_date_of(ts) == date(2026, 5, 28)


def test_live_date_of_at_4am_is_same_day():
    ts = _utc_naive(2026, 5, 29, 4, 0)
    assert live_date_of(ts) == date(2026, 5, 29)


def test_current_live_window_after_4am():
    now = _utc_naive(2026, 5, 29, 10, 0)
    live_date, start_utc = current_live_window(now)
    assert live_date == date(2026, 5, 29)
    # 起点 = CST 2026-05-29 04:00 == UTC 2026-05-28 20:00
    assert start_utc == datetime(2026, 5, 28, 20, 0)


def test_current_live_window_before_4am_rolls_back():
    now = _utc_naive(2026, 5, 29, 2, 0)
    live_date, start_utc = current_live_window(now)
    assert live_date == date(2026, 5, 28)
    assert start_utc == datetime(2026, 5, 27, 20, 0)
