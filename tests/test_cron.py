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


def test_archive_removes_old_rows(tmp_db):
    """raw_retention_days=30 默认；35 天前的 raw 应被清，30 天内保留。"""
    from sb2099.db import SessionLocal

    now = datetime.utcnow().replace(microsecond=0)
    _persist_sync(_evt("recent", "u1", now - timedelta(days=10)))
    _persist_sync(_evt("old", "u2", now - timedelta(days=35)))

    removed = _archive_sync()
    assert removed == 1
    with SessionLocal() as s:
        contents = [r.content_raw for r in s.execute(select(RawDanmaku)).scalars().all()]
        assert contents == ["recent"]
