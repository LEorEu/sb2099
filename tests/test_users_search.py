"""GET /api/users/search 端点：q 长度门槛、昵称/uid 双模、返回字段。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from sb2099 import db as _db
from sb2099.models import User


@pytest.fixture
def client(tmp_db):
    from tests.conftest import build_test_app
    from sb2099.ratelimit import limiter
    limiter.reset()
    return TestClient(build_test_app())


def _seed_users(rows):
    """rows: [(uid, nickname, avatar_path, last_seen_offset_days)]"""
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        for uid, nick, av, days in rows:
            ts = now - timedelta(days=days)
            s.add(User(uid=uid, nickname=nick, avatar=av,
                       first_seen=ts, last_seen=ts, source="seed"))
        s.commit()


def test_q_too_short_returns_empty(client):
    _seed_users([("100", "小明", "avatar_v3/1", 1)])
    r = client.get("/api/users/search?q=")
    assert r.status_code == 200
    assert r.json() == {"results": []}
    r = client.get("/api/users/search?q=ab")
    assert r.json() == {"results": []}


def test_nickname_partial_match(client):
    _seed_users([
        ("100", "桜洛洛洛洛", "avatar_v3/1", 1),
        ("200", "另一个用户", "avatar_v3/2", 2),
        ("300", "桜花满开了", "avatar_v3/3", 3),
    ])
    # q 必须 > 2 字符；用三字 "桜洛洛" 模糊匹配
    r = client.get("/api/users/search?q=桜洛洛")
    results = r.json()["results"]
    assert len(results) == 1
    assert results[0]["nickname"] == "桜洛洛洛洛"


def test_q_exactly_two_chars_rejected(client):
    _seed_users([("100", "小桜花", None, 1)])
    r = client.get("/api/users/search?q=小桜")
    assert r.json() == {"results": []}


def test_returns_uid_nickname_avatar_url(client):
    _seed_users([("12345678", "测试用户名", "avatar_v3/202605/abc", 1)])
    r = client.get("/api/users/search?q=测试用")
    item = r.json()["results"][0]
    assert item["uid"] == "12345678"
    assert item["nickname"] == "测试用户名"
    assert item["avatar"] == "https://apic.douyucdn.cn/upload/avatar_v3/202605/abc_middle.jpg"


def test_numeric_q_searches_uid_prefix(client):
    _seed_users([
        ("123456789", "用户A", None, 1),
        ("987654321", "用户B", None, 2),
    ])
    r = client.get("/api/users/search?q=1234")
    results = r.json()["results"]
    assert len(results) == 1
    assert results[0]["uid"] == "123456789"


def test_order_by_last_seen_desc(client):
    _seed_users([
        ("100", "活跃用户甲", None, 5),
        ("200", "活跃用户乙", None, 1),  # 更近
        ("300", "活跃用户丙", None, 3),
    ])
    r = client.get("/api/users/search?q=活跃用户")
    uids = [x["uid"] for x in r.json()["results"]]
    assert uids == ["200", "300", "100"]


def test_avatar_none_returns_none(client):
    _seed_users([("100", "无头像的人", None, 1)])
    r = client.get("/api/users/search?q=无头像")
    assert r.json()["results"][0]["avatar"] is None
