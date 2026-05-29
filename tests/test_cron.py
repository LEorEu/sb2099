"""cron: recount 构建 daily_hot + archive 清理。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from sb2099.cron import _archive_sync, _recount_sync
from sb2099.ingest.aggregator import _persist_sync
from sb2099.models import DailyHot, RawDanmaku
from sb2099.settings import settings_cache


def _evt(content: str, uid: str, ts: datetime) -> dict:
    return {
        "ts": int(ts.replace(tzinfo=timezone.utc).timestamp() * 1000),
        "room_id": 12740109,
        "kind": "chat",
        "uid": uid,
        "nickname": "t",
        "content": content,
        "color": None,
    }


def _set_threshold(value: int) -> None:
    import json
    from datetime import datetime as _dt
    from sb2099.db import SessionLocal
    from sb2099.models import Setting
    with SessionLocal() as s:
        s.execute(
            update(Setting)
            .where(Setting.key == "live_hot_min_unique_senders_24h")
            .values(value=json.dumps(value), updated_at=_dt.utcnow())
        )
        s.commit()
    settings_cache.invalidate()


def test_recount_promotes_when_threshold_met(tmp_db):
    from sb2099.db import SessionLocal
    _set_threshold(2)
    now = datetime.utcnow().replace(microsecond=0)
    _persist_sync(_evt("加一", "u1", now - timedelta(minutes=1)))
    _persist_sync(_evt("加一", "u2", now - timedelta(minutes=2)))
    _persist_sync(_evt("加一", "u3", now - timedelta(minutes=3)))

    _recount_sync()
    with SessionLocal() as s:
        row = s.execute(select(DailyHot)).scalar_one()
        assert row.content_norm == "加一"
        assert row.send_cnt == 3
        assert row.unique_sender_cnt == 3


def test_recount_skips_below_threshold(tmp_db):
    from sb2099.db import SessionLocal
    _set_threshold(3)
    now = datetime.utcnow().replace(microsecond=0)
    _persist_sync(_evt("没火", "u1", now - timedelta(minutes=1)))
    _persist_sync(_evt("没火", "u2", now - timedelta(minutes=2)))

    _recount_sync()
    with SessionLocal() as s:
        assert s.execute(select(DailyHot)).scalars().all() == []


def test_recount_skips_noise(tmp_db):
    from sb2099.db import SessionLocal
    _set_threshold(2)
    now = datetime.utcnow().replace(microsecond=0)
    _persist_sync(_evt("+1", "u1", now - timedelta(minutes=1)))
    _persist_sync(_evt("+1", "u2", now - timedelta(minutes=2)))

    _recount_sync()
    with SessionLocal() as s:
        assert s.execute(select(DailyHot)).scalars().all() == []


def test_archive_removes_old_raw_and_daily_hot(tmp_db):
    """raw_retention_days=2（迁移后默认）：3 天前 raw 删、1 天前保留；
    daily_hot_retention_days=7：8 天前的数据日行删、今天保留。"""
    from sb2099.db import SessionLocal
    from sb2099.models import DailyHot

    now = datetime.utcnow().replace(microsecond=0)
    _persist_sync(_evt("recent", "u1", now - timedelta(days=1)))
    _persist_sync(_evt("old", "u2", now - timedelta(days=3)))

    today = now.date().isoformat()
    old_date = (now.date() - timedelta(days=8)).isoformat()
    with SessionLocal() as s:
        s.add(DailyHot(live_date=today, content_norm="keep", content_sample="keep",
                       send_cnt=5, unique_sender_cnt=5, first_seen=now, last_seen=now,
                       page_copy_cnt=0, is_filtered=False))
        s.add(DailyHot(live_date=old_date, content_norm="drop", content_sample="drop",
                       send_cnt=5, unique_sender_cnt=5, first_seen=now, last_seen=now,
                       page_copy_cnt=0, is_filtered=False))
        s.commit()

    removed = _archive_sync()
    assert removed == 1  # 只删了 3 天前那条 raw
    with SessionLocal() as s:
        raw_contents = [r.content_raw for r in s.execute(select(RawDanmaku)).scalars().all()]
        assert raw_contents == ["recent"]
        hot_dates = [d.live_date for d in s.execute(select(DailyHot)).scalars().all()]
        assert hot_dates == [today]
