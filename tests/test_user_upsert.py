"""aggregator.persist_user_from_chat 的同步路径单测。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sb2099 import db as _db
from sb2099.ingest.aggregator import _persist_user_sync, persist_user_from_chat
from sb2099.models import User


def _evt(uid="100", nickname="昵称A", ic="avatar_v3/202605/aaa", ts_ms=None):
    if ts_ms is None:
        ts_ms = int(datetime(2026, 5, 29, 12, 0, 0).timestamp() * 1000)
    return {
        "ts": ts_ms,
        "kind": "chat",
        "uid": uid,
        "nickname": nickname,
        "content": "hi",
        "color": None,
        "ic": ic,
        "level": 10,
        "bnn": None,
        "brid": None,
        "bl": None,
        "dms": None,
    }


def test_new_user_inserted_with_source_live(tmp_db):
    _persist_user_sync(_evt())
    with _db.SessionLocal() as s:
        u = s.get(User, "100")
    assert u is not None
    assert u.nickname == "昵称A"
    assert u.avatar == "avatar_v3/202605/aaa"
    assert u.source == "live"


def test_seed_source_preserved_on_upsert(tmp_db):
    # 预置一条 source=seed
    now = datetime(2026, 5, 29, 10, 0, 0)
    with _db.SessionLocal() as s:
        s.add(User(uid="200", nickname="旧名", avatar="avatar/default/1",
                   first_seen=now, last_seen=now, source="seed"))
        s.commit()

    _persist_user_sync(_evt(uid="200", nickname="新名", ic="avatar_v3/2026/new",
                            ts_ms=int(now.timestamp() * 1000) + 60_000))
    with _db.SessionLocal() as s:
        u = s.get(User, "200")
    # source 不被覆盖（保留 seed）
    assert u.source == "seed"
    assert u.nickname == "新名"
    assert u.avatar == "avatar_v3/2026/new"


def test_null_fields_dont_overwrite_existing(tmp_db):
    # 已有昵称和头像
    _persist_user_sync(_evt(uid="300", nickname="原始", ic="avatar_v3/2026/orig"))
    # 后来一条 nickname/ic 都为 None
    later = int(datetime(2026, 5, 29, 13, 0, 0).timestamp() * 1000)
    _persist_user_sync(_evt(uid="300", nickname=None, ic=None, ts_ms=later))
    with _db.SessionLocal() as s:
        u = s.get(User, "300")
    assert u.nickname == "原始"
    assert u.avatar == "avatar_v3/2026/orig"


def test_missing_uid_is_noop(tmp_db):
    evt = _evt()
    evt["uid"] = None
    _persist_user_sync(evt)  # 不应抛
    with _db.SessionLocal() as s:
        n = s.query(User).count()
    assert n == 0


def test_async_wrapper_invokes_sync(tmp_db):
    asyncio.run(persist_user_from_chat(_evt(uid="400")))
    with _db.SessionLocal() as s:
        assert s.get(User, "400") is not None
