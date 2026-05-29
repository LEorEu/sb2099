"""aggregator: 只把 chat 事件写入 raw_danmaku（不再聚合 live_hot）。"""
from __future__ import annotations

from sqlalchemy import select

from sb2099.ingest.aggregator import _persist_sync
from sb2099.models import RawDanmaku


def _evt(content: str, uid: str = "u1", ts_ms: int = 1779530000000) -> dict:
    return {
        "ts": ts_ms,
        "room_id": 12740109,
        "kind": "chat",
        "uid": uid,
        "nickname": "test",
        "content": content,
        "color": None,
    }


def test_chat_inserts_raw(tmp_db):
    from sb2099.db import SessionLocal
    _persist_sync(_evt("打 rl"))
    with SessionLocal() as s:
        rows = s.execute(select(RawDanmaku)).scalars().all()
        assert len(rows) == 1
        assert rows[0].content_raw == "打 rl"
        assert rows[0].uid == "u1"


def test_repeat_inserts_multiple_raw(tmp_db):
    from sb2099.db import SessionLocal
    for i in range(5):
        _persist_sync(_evt("加一", uid=f"u{i}", ts_ms=1779530000000 + i * 1000))
    with SessionLocal() as s:
        assert len(s.execute(select(RawDanmaku)).scalars().all()) == 5


def test_normalized_value_stored(tmp_db):
    from sb2099.db import SessionLocal
    _persist_sync(_evt("打ｒｌ"))
    with SessionLocal() as s:
        row = s.execute(select(RawDanmaku)).scalar_one()
        assert row.content_norm == "打rl"


def test_empty_content_dropped(tmp_db):
    from sb2099.db import SessionLocal
    _persist_sync(_evt(""))
    _persist_sync(_evt("   "))
    with SessionLocal() as s:
        assert s.execute(select(RawDanmaku)).scalars().all() == []
