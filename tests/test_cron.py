"""cron.recount_once：基于 raw_danmaku 重算 live_hot 计数。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from sb2099.cron import _archive_sync, _recount_sync
from sb2099.ingest.aggregator import _persist_sync
from sb2099.models import LiveHot, RawDanmaku


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


def test_recount_send_cnt_24h(tmp_db):
    from sb2099.db import SessionLocal

    now = datetime.utcnow().replace(microsecond=0)
    # 3 次"加一"——24h 内 2 次（同 uid 不算 unique 增量），1 次 26h 前
    _persist_sync(_evt("加一", "u1", now - timedelta(hours=1)))
    _persist_sync(_evt("加一", "u2", now - timedelta(hours=2)))
    _persist_sync(_evt("加一", "u3", now - timedelta(hours=26)))

    _recount_sync()
    with SessionLocal() as s:
        row = s.execute(select(LiveHot)).scalar_one()
        assert row.send_cnt_total == 3
        assert row.send_cnt_24h == 2
        assert row.send_cnt_7d == 3
        assert row.unique_sender_cnt_24h == 2
        assert row.unique_sender_cnt_7d == 3


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
