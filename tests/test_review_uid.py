"""submission.review_uid 三探测器单测。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sb2099 import db as _db
from sb2099.models import Barrage, RawDanmaku, User
from sb2099.settings import settings_cache
from sb2099.submission import review_uid


def _add_user(uid="123"):
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        s.add(User(uid=uid, nickname=f"nick{uid}", avatar=None,
                   first_seen=now, last_seen=now, source="live"))
        s.commit()


def _add_raw(uid, content="hi", ts=None):
    if ts is None:
        ts = datetime.utcnow()
    with _db.SessionLocal() as s:
        s.add(RawDanmaku(ts=ts, uid=uid, nickname="x",
                         content_raw=content, content_norm=content))
        s.commit()


def _add_barrage(uid, ip_hash, ts=None):
    if ts is None:
        ts = datetime.utcnow()
    with _db.SessionLocal() as s:
        s.add(Barrage(content=f"c-{ip_hash}", content_norm=f"cn-{ip_hash}-{ts.isoformat()}",
                      tags="00", source="user", submitter_ip_hash=ip_hash,
                      submitter_uid=uid, submit_time=ts, cnt=0, report_cnt=0,
                      status="active"))
        s.commit()


def test_anonymous_passes_through(tmp_db):
    with _db.SessionLocal() as s:
        pending, reason = review_uid(s, None, "iphash1")
    assert pending is False
    assert reason is None


def test_disabled_by_setting(tmp_db):
    import json
    from sb2099.models import Setting
    with _db.SessionLocal() as s:
        s.execute(
            Setting.__table__.update()
            .where(Setting.key == "submission_anti_fraud_enabled")
            .values(value=json.dumps(False), updated_at=datetime.utcnow())
        )
        s.commit()
    settings_cache.invalidate()
    with _db.SessionLocal() as s:
        pending, reason = review_uid(s, "999", "iphash1")
    assert pending is False


def test_uid_never_seen_in_room(tmp_db):
    _add_user("123")
    # 没有 raw_danmaku 记录
    with _db.SessionLocal() as s:
        pending, reason = review_uid(s, "123", "iphash1")
    assert pending is True
    assert reason == "uid_never_seen_in_room"


def test_uid_inactive_recent(tmp_db):
    _add_user("123")
    _add_raw("123", ts=datetime.utcnow() - timedelta(days=60))
    with _db.SessionLocal() as s:
        pending, reason = review_uid(s, "123", "iphash1")
    assert pending is True
    assert reason.startswith("uid_inactive_")


def test_uid_active_within_window(tmp_db):
    _add_user("123")
    _add_raw("123", ts=datetime.utcnow() - timedelta(hours=2))
    with _db.SessionLocal() as s:
        pending, reason = review_uid(s, "123", "iphash1")
    assert pending is False


def test_uid_multi_ip_hashes_triggers(tmp_db):
    _add_user("123")
    _add_raw("123", ts=datetime.utcnow() - timedelta(hours=1))
    # 已有 4 个不同 IP 的历史投稿；本次再加 1 个不同的 → 5 个 ≥ 阈值 5
    for i in range(4):
        _add_barrage("123", ip_hash=f"hash{i}", ts=datetime.utcnow() - timedelta(days=i))
    with _db.SessionLocal() as s:
        pending, reason = review_uid(s, "123", "hashNEW")
    assert pending is True
    assert reason.startswith("uid_distinct_ip_hashes_")


def test_uid_multi_ip_below_threshold(tmp_db):
    _add_user("123")
    _add_raw("123", ts=datetime.utcnow() - timedelta(hours=1))
    for i in range(3):
        _add_barrage("123", ip_hash=f"hash{i}", ts=datetime.utcnow() - timedelta(days=i))
    # 同一 IP 重复投稿，distinct hash 还是 3
    with _db.SessionLocal() as s:
        pending, reason = review_uid(s, "123", "hash0")
    assert pending is False
