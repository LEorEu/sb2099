"""aggregator: raw_danmaku 入库 + live_hot upsert + 噪音过滤。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select, update

from sb2099.ingest.aggregator import _persist_sync
from sb2099.models import LiveHot, RawDanmaku, Setting


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


def test_first_chat_creates_live_hot(tmp_db):
    from sb2099.db import SessionLocal
    _persist_sync(_evt("打 rl"))
    with SessionLocal() as s:
        assert s.execute(select(RawDanmaku)).scalars().all()
        rows = s.execute(select(LiveHot)).scalars().all()
        assert len(rows) == 1
        r = rows[0]
        assert r.content_sample == "打 rl"
        assert r.send_cnt_total == 1
        assert r.is_filtered is False


def test_repeat_increments_total(tmp_db):
    from sb2099.db import SessionLocal
    for i in range(5):
        _persist_sync(_evt("加一", uid=f"u{i}", ts_ms=1779530000000 + i * 1000))
    with SessionLocal() as s:
        rows = s.execute(select(LiveHot)).scalars().all()
        assert len(rows) == 1
        assert rows[0].send_cnt_total == 5
        # raw_danmaku 5 行
        assert len(s.execute(select(RawDanmaku)).scalars().all()) == 5


def test_normalized_dedup(tmp_db):
    """全角字母 / 零宽 → 应当合并到同一条 live_hot。"""
    from sb2099.db import SessionLocal
    _persist_sync(_evt("打ｒｌ"))
    _persist_sync(_evt("打​rl", uid="u2", ts_ms=1779530001000))
    with SessionLocal() as s:
        rows = s.execute(select(LiveHot)).scalars().all()
        assert len(rows) == 1
        assert rows[0].send_cnt_total == 2


def test_noise_filter_marks_is_filtered(tmp_db):
    """命中 live_noise_filters 子串 → live_hot 行 is_filtered=1。"""
    from sb2099.db import SessionLocal
    from sb2099.settings import settings_cache

    # DEFAULTS 已含 "+1"；直接喂含子串的内容
    settings_cache.invalidate()
    _persist_sync(_evt("+1+1+1"))
    with SessionLocal() as s:
        rows = s.execute(select(LiveHot)).scalars().all()
        assert len(rows) == 1
        assert rows[0].is_filtered is True


def test_noise_filter_runtime_update(tmp_db):
    """改 setting 后 invalidate → 新规则立刻生效。"""
    from sb2099.db import SessionLocal
    from sb2099.settings import settings_cache

    settings_cache.invalidate()
    # 第一条不命中默认规则
    _persist_sync(_evt("奇怪的内容ABC"))
    with SessionLocal() as s:
        first = s.execute(select(LiveHot)).scalar_one()
        assert first.is_filtered is False

        s.execute(
            update(Setting)
            .where(Setting.key == "live_noise_filters")
            .values(value=json.dumps(["奇怪"]), updated_at=datetime.utcnow())
        )
        s.commit()

    settings_cache.invalidate()
    _persist_sync(_evt("奇怪的内容ABC", uid="u2", ts_ms=1779530002000))
    with SessionLocal() as s:
        row = s.execute(select(LiveHot)).scalar_one()
        # 一旦命中过 noise，is_filtered 保持 1
        assert row.send_cnt_total == 2
        assert row.is_filtered is True


def test_empty_content_dropped(tmp_db):
    from sb2099.db import SessionLocal
    _persist_sync(_evt(""))
    _persist_sync(_evt("   "))  # 归一化后为空
    with SessionLocal() as s:
        assert s.execute(select(LiveHot)).scalars().all() == []
        assert s.execute(select(RawDanmaku)).scalars().all() == []
