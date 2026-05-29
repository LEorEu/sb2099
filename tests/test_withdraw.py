"""撤回端点 + HMAC cookie 单测。"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from sb2099 import db as _db
from sb2099.models import Barrage


@pytest.fixture
def client(tmp_db):
    from tests.conftest import build_test_app
    from sb2099.ratelimit import limiter
    limiter.reset()
    return TestClient(build_test_app())


def _submit_active(client, content="一条新烂梗", uid=None):
    r = client.post(
        "/api/barrage",
        json={"content": content, "tags": ["00"], "submitter_uid": uid},
    )
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["status"] == "active"
    return body


def test_submit_sets_recent_cookie(client):
    body = _submit_active(client)
    bid = body["id"]
    # TestClient 自动持久化 server-set cookies 到 client.cookies
    assert f"sb_recent_{bid}" in client.cookies


def test_withdraw_with_valid_cookie_deletes(client):
    body = _submit_active(client)
    bid = body["id"]
    r = client.delete(f"/api/submission/{bid}/withdraw")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["withdrawn"] is True
    with _db.SessionLocal() as s:
        assert s.get(Barrage, bid) is None


def test_withdraw_without_cookie_rejected(client):
    body = _submit_active(client)
    bid = body["id"]
    # 清掉 cookie
    client.cookies.clear()
    r = client.delete(f"/api/submission/{bid}/withdraw")
    assert r.status_code == 404
    with _db.SessionLocal() as s:
        assert s.get(Barrage, bid) is not None


def test_withdraw_with_tampered_token_rejected(client):
    body = _submit_active(client)
    bid = body["id"]
    client.cookies.set(
        f"sb_recent_{bid}",
        "deadbeef" + "." + str(int(time.time()) + 60),
    )
    r = client.delete(f"/api/submission/{bid}/withdraw")
    assert r.status_code == 403


def test_withdraw_expired_token_rejected(client):
    body = _submit_active(client)
    bid = body["id"]
    # 把 cookie 换成一个 expires_at 已过去的合法签名（通过私 API 生成）
    from sb2099.web.routes_api import _hmac_token
    from sb2099.ratelimit import ip_hash, extract_ip
    # client 默认 IP 是 testserver；用 sha256 替我们计算 ip_hash
    # 用一个我们知道是签发主体的 ip_hash → 走真实 extract_ip 流程：
    # TestClient 把请求 ip 设为 "testclient"
    real_ip_hash = ip_hash("testclient")
    past_exp = int(time.time()) - 5
    token = _hmac_token(bid, real_ip_hash, past_exp)
    client.cookies.set(f"sb_recent_{bid}", token)
    r = client.delete(f"/api/submission/{bid}/withdraw")
    assert r.status_code == 410


def test_withdraw_idempotent_when_already_gone(client):
    """admin 已先软删/物理删时，撤回不应 500。"""
    body = _submit_active(client)
    bid = body["id"]
    with _db.SessionLocal() as s:
        s.delete(s.get(Barrage, bid))
        s.commit()
    r = client.delete(f"/api/submission/{bid}/withdraw")
    assert r.status_code == 200
    assert r.json()["data"]["already_gone"] is True
