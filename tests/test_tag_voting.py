"""Tag 投票：unit (tag_voting 模块) + integration (vote-tag / propose-tag 端点 + admin approve)。"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from sb2099 import db as _db
from sb2099.models import Barrage, BarrageTagVote, Tag, User
from sb2099.tag_voting import settle_all_for_tag, settle_tag, vote_count, vote_threshold


@pytest.fixture
def client(tmp_db):
    from tests.conftest import build_test_app
    from sb2099.ratelimit import limiter
    limiter.reset()
    return TestClient(build_test_app())


def _add_barrage(content="一条投稿", tags="00"):
    with _db.SessionLocal() as s:
        b = Barrage(
            content=content,
            content_norm=content,
            tags=tags,
            source="user",
            submit_time=datetime.utcnow(),
            status="active",
        )
        s.add(b)
        s.commit()
        s.refresh(b)
        return b.id


def _add_user(uid):
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        s.add(User(uid=uid, nickname=f"u{uid}", first_seen=now, last_seen=now, source="seed"))
        s.commit()


def _vote_row(barrage_id, tag_value, voter_uid=None, voter_ip_hash="ip1"):
    return BarrageTagVote(
        barrage_id=barrage_id,
        tag_value=tag_value,
        voter_uid=voter_uid,
        voter_ip_hash=voter_ip_hash,
        ts=datetime.utcnow(),
    )


# ---- unit: tag_voting --------------------------------------------------


def test_vote_count_dedup_by_uid_and_ip(tmp_db):
    bid = _add_barrage()
    _add_user("u1")
    _add_user("u2")
    with _db.SessionLocal() as s:
        # 同一 uid 重复投 → 仍只算 1（PK 拦截）
        s.add(_vote_row(bid, "00", voter_uid="u1", voter_ip_hash="ip1"))
        s.commit()
        # 不同 uid 另一票
        s.add(_vote_row(bid, "00", voter_uid="u2", voter_ip_hash="ip1"))
        s.commit()
        # 匿名 IP 一票（ip2 跟前面 uid 路径不冲突）
        s.add(_vote_row(bid, "00", voter_uid=None, voter_ip_hash="ip2"))
        s.commit()
        assert vote_count(s, bid, "00") == 3


def test_vote_threshold_reads_setting(tmp_db):
    # 默认 3（迁移 0009 写入）
    assert vote_threshold() == 3


def test_settle_tag_appends_only_when_above_threshold(tmp_db):
    bid = _add_barrage(tags="00")
    with _db.SessionLocal() as s:
        # 2 票，未达 3 阈值
        s.add(_vote_row(bid, "01", voter_ip_hash="a"))
        s.add(_vote_row(bid, "01", voter_ip_hash="b"))
        s.commit()
        assert settle_tag(s, bid, "01") is False
        # 第 3 票达阈值
        s.add(_vote_row(bid, "01", voter_ip_hash="c"))
        s.commit()
        assert settle_tag(s, bid, "01") is True
        s.commit()
        assert "01" in s.get(Barrage, bid).tags.split(",")
        # 再次结算幂等
        assert settle_tag(s, bid, "01") is False


def test_settle_all_for_tag_backfills(tmp_db):
    b1 = _add_barrage(content="m1", tags="00")
    b2 = _add_barrage(content="m2", tags="00")
    b3 = _add_barrage(content="m3", tags="00")
    with _db.SessionLocal() as s:
        # b1: 3 票满阈值；b2: 2 票不够；b3: 没人投
        for ip in ("a", "b", "c"):
            s.add(_vote_row(b1, "02", voter_ip_hash=ip))
        for ip in ("d", "e"):
            s.add(_vote_row(b2, "02", voter_ip_hash=ip))
        s.commit()
        added = settle_all_for_tag(s, "02")
        s.commit()
        assert added == 1
        assert "02" in s.get(Barrage, b1).tags.split(",")
        assert "02" not in s.get(Barrage, b2).tags.split(",")
        assert "02" not in s.get(Barrage, b3).tags.split(",")


# ---- integration: vote-tag endpoint -------------------------------------


def test_vote_tag_basic_flow(client, tmp_db):
    bid = _add_barrage(tags="00")
    r = client.post(f"/api/barrage/{bid}/vote-tag", json={"tag_value": "01"})
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["count"] == 1
    assert body["threshold"] == 3
    assert body["applied"] is False
    assert body["pending_approval"] is False


def test_vote_tag_threshold_hit_applies(client, tmp_db):
    bid = _add_barrage(tags="00")
    # 3 个不同 IP 投同一个 tag → 第 3 次返回 applied=True
    with TestClient(client.app) as c:
        pass
    # 用相同 client 的不同 X-Forwarded-For
    for i, ip in enumerate(("1.1.1.1", "2.2.2.2", "3.3.3.3"), start=1):
        r = client.post(
            f"/api/barrage/{bid}/vote-tag",
            json={"tag_value": "01"},
            headers={"X-Forwarded-For": ip},
        )
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["count"] == i
        assert body["applied"] is (i >= 3)
    with _db.SessionLocal() as s:
        row = s.get(Barrage, bid)
        assert "01" in row.tags.split(",")


def test_vote_tag_dedup_same_ip(client, tmp_db):
    bid = _add_barrage(tags="00")
    for _ in range(3):
        r = client.post(
            f"/api/barrage/{bid}/vote-tag",
            json={"tag_value": "01"},
            headers={"X-Forwarded-For": "1.1.1.1"},
        )
        assert r.status_code == 200
    # 同 IP 投三次仍只算 1 票
    assert r.json()["data"]["count"] == 1
    assert r.json()["data"]["applied"] is False


def test_vote_tag_unknown_tag_404(client, tmp_db):
    bid = _add_barrage(tags="00")
    r = client.post(f"/api/barrage/{bid}/vote-tag", json={"tag_value": "xxx"})
    assert r.status_code == 404


def test_vote_tag_invalid_barrage_404(client, tmp_db):
    r = client.post("/api/barrage/99999/vote-tag", json={"tag_value": "01"})
    assert r.status_code == 404


def test_vote_tag_uid_validated_via_user_table(client, tmp_db):
    """前端传上来的 uid 在 user 表里不存在时应回退匿名（不报错）。"""
    bid = _add_barrage(tags="00")
    r = client.post(
        f"/api/barrage/{bid}/vote-tag",
        json={"tag_value": "01", "voter_uid": "ghost_uid"},
    )
    assert r.status_code == 200
    # 此时应该按 IP hash 落账，不按 uid
    with _db.SessionLocal() as s:
        rows = s.query(BarrageTagVote).filter_by(barrage_id=bid, tag_value="01").all()
        assert len(rows) == 1
        assert rows[0].voter_uid is None  # 回退匿名


# ---- integration: propose-tag endpoint -----------------------------------


def test_propose_tag_creates_pending_and_self_votes(client, tmp_db):
    bid = _add_barrage(tags="00")
    r = client.post(
        f"/api/barrage/{bid}/propose-tag",
        json={"value": "newt", "label": "新标签"},
    )
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["pending_approval"] is True
    assert body["count"] == 1
    with _db.SessionLocal() as s:
        tag = s.get(Tag, "newt")
        assert tag is not None
        assert tag.enabled is False
        assert tag.proposed_at is not None


def test_propose_existing_enabled_tag_conflict(client, tmp_db):
    bid = _add_barrage(tags="00")
    r = client.post(
        f"/api/barrage/{bid}/propose-tag",
        json={"value": "00", "label": "存在"},
    )
    assert r.status_code == 409


def test_propose_invalid_value_rejected(client, tmp_db):
    bid = _add_barrage(tags="00")
    r = client.post(
        f"/api/barrage/{bid}/propose-tag",
        json={"value": "with space", "label": "x"},
    )
    assert r.status_code == 422  # pydantic validation


# ---- integration: admin approve flow -------------------------------------


def _admin_client(client):
    """登录 admin 后用同一个 client。"""
    token = "test_token_" + "x" * 16
    r = client.post("/api/admin/login", json={"token": token})
    assert r.status_code == 200
    return client


def test_admin_approve_backfills_threshold_hits(client, tmp_db):
    bid_pass = _add_barrage(content="pass", tags="00")
    bid_fail = _add_barrage(content="fail", tags="00")
    # 提议 + 3 票（pass） / 2 票（fail）
    for i, ip in enumerate(("1.1.1.1", "2.2.2.2", "3.3.3.3")):
        client.post(
            f"/api/barrage/{bid_pass}/propose-tag" if i == 0 else f"/api/barrage/{bid_pass}/vote-tag",
            json={"value": "wow", "label": "厉害"} if i == 0 else {"tag_value": "wow"},
            headers={"X-Forwarded-For": ip},
        )
    for ip in ("4.4.4.4", "5.5.5.5"):
        client.post(
            f"/api/barrage/{bid_fail}/vote-tag",
            json={"tag_value": "wow"},
            headers={"X-Forwarded-For": ip},
        )
    # admin 批准
    _admin_client(client)
    r = client.post("/api/admin/tags/wow/approve")
    assert r.status_code == 200
    with _db.SessionLocal() as s:
        assert s.get(Tag, "wow").enabled is True
        assert "wow" in s.get(Barrage, bid_pass).tags.split(",")
        assert "wow" not in s.get(Barrage, bid_fail).tags.split(",")


def test_admin_delete_pending_clears_votes(client, tmp_db):
    bid = _add_barrage(tags="00")
    client.post(
        f"/api/barrage/{bid}/propose-tag",
        json={"value": "trash", "label": "废"},
        headers={"X-Forwarded-For": "1.1.1.1"},
    )
    _admin_client(client)
    r = client.delete("/api/admin/tags/trash")
    assert r.status_code == 200
    with _db.SessionLocal() as s:
        assert s.get(Tag, "trash") is None
        cnt = s.query(BarrageTagVote).filter_by(tag_value="trash").count()
        assert cnt == 0
