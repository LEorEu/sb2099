"""/api/admin/* JSON 后台：登录守卫、设置、标签 CRUD、待审/反馈/回收站、直播热门、统计。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from sb2099 import db as _db
from sb2099.models import Barrage, BarrageReport, DailyHot, RawDanmaku, Tag


ADMIN_TOKEN = "test_token_" + "x" * 16  # 与 conftest monkeypatch 一致


@pytest.fixture
def client(tmp_db):
    from tests.conftest import build_test_app
    from sb2099.ratelimit import limiter
    limiter.reset()
    return TestClient(build_test_app(), follow_redirects=False)


@pytest.fixture
def admin_client(client):
    r = client.post("/api/admin/login", json={"token": ADMIN_TOKEN})
    assert r.status_code == 200
    return client


def _make_barrage(status="pending", content="test", tags="00") -> int:
    with _db.SessionLocal() as s:
        b = Barrage(content=content, content_norm=content, tags=tags, source="user",
                    submit_time=datetime.utcnow(), status=status)
        s.add(b)
        s.commit()
        return b.id


def _current_live_date_iso():
    from datetime import timezone
    from sb2099.live_day import current_live_window
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ld, _ = current_live_window(now)
    return ld.isoformat()


# ---- auth -----------------------------------------------------------------


def test_login_wrong_token_401(client):
    r = client.post("/api/admin/login", json={"token": "nope"})
    assert r.status_code == 401


def test_login_sets_httponly_cookie(client):
    r = client.post("/api/admin/login", json={"token": ADMIN_TOKEN})
    assert r.status_code == 200
    sc = r.headers.get("set-cookie", "")
    assert "sb2099_admin=" in sc and "HttpOnly" in sc
    assert "samesite=strict" in sc.lower()


def test_me_requires_login(client):
    assert client.get("/api/admin/me").status_code == 401


def test_me_ok_when_logged_in(admin_client):
    r = admin_client.get("/api/admin/me")
    assert r.status_code == 200 and r.json()["authenticated"] is True


def test_logout_clears_cookie(admin_client):
    r = admin_client.post("/api/admin/logout")
    assert r.status_code == 200
    # cookie 清除后再访问受保护端点应 401
    admin_client.cookies.clear()
    assert admin_client.get("/api/admin/me").status_code == 401


def test_protected_endpoints_401_when_logged_out(client):
    assert client.get("/api/admin/settings").status_code == 401
    assert client.get("/api/admin/stats").status_code == 401
    assert client.post("/api/admin/tags", json={"value": "09", "label": "x"}).status_code == 401


# ---- settings -------------------------------------------------------------


def test_settings_get_returns_typed_items(admin_client):
    r = admin_client.get("/api/admin/settings")
    assert r.status_code == 200
    items = {it["key"]: it for it in r.json()["items"]}
    assert items["live_noise_filters"]["kind"] == "lines"
    assert isinstance(items["live_noise_filters"]["value"], list)
    assert items["barrage_max_length"]["kind"] == "int"


def test_settings_put_writes_and_invalidates(admin_client):
    from sb2099.settings import settings_cache
    r = admin_client.put("/api/admin/settings", json={
        "values": {"live_noise_filters": ["晚安", "  好梦  ", ""], "barrage_max_length": "500"}
    })
    assert r.status_code == 200
    assert settings_cache.get("live_noise_filters") == ["晚安", "好梦"]
    assert settings_cache.get("barrage_max_length") == 500


def test_settings_put_accepts_int_typed(admin_client):
    from sb2099.settings import settings_cache
    r = admin_client.put("/api/admin/settings", json={"values": {"barrage_min_length": 7}})
    assert r.status_code == 200
    assert settings_cache.get("barrage_min_length") == 7


def test_settings_put_rejects_non_integer(admin_client):
    r = admin_client.put("/api/admin/settings", json={"values": {"barrage_max_length": "abc"}})
    assert r.status_code == 422
    assert "barrage_max_length" in str(r.json()["detail"])


def test_settings_put_empty_lines_ok(admin_client):
    from sb2099.settings import settings_cache
    r = admin_client.put("/api/admin/settings", json={"values": {"live_noise_filters": []}})
    assert r.status_code == 200
    assert settings_cache.get("live_noise_filters") == []


# ---- tags -----------------------------------------------------------------


def test_tags_crud(admin_client):
    r = admin_client.post("/api/admin/tags",
                          json={"value": "08", "label": "新 tag", "sort": 5})
    assert r.status_code == 201
    with _db.SessionLocal() as s:
        assert s.get(Tag, "08").label == "新 tag"

    r = admin_client.patch("/api/admin/tags/08",
                           json={"label": "改了", "icon_url": "https://x/y.png",
                                 "sort": 9, "enabled": False})
    assert r.status_code == 200
    with _db.SessionLocal() as s:
        row = s.get(Tag, "08")
        assert row.label == "改了" and row.icon_url == "https://x/y.png" and row.enabled is False

    r = admin_client.delete("/api/admin/tags/08")
    assert r.status_code == 200
    with _db.SessionLocal() as s:
        assert s.get(Tag, "08") is None


def test_tags_create_bad_value_400(admin_client):
    r = admin_client.post("/api/admin/tags", json={"value": "bad value", "label": "x"})
    assert r.status_code == 400


def test_tags_create_duplicate_409(admin_client):
    r = admin_client.post("/api/admin/tags", json={"value": "00", "label": "重复"})
    assert r.status_code == 409


def test_tags_list_includes_pending_stats(admin_client):
    bid = _make_barrage("active", "t", "00")
    r = admin_client.post(f"/api/barrage/{bid}/propose-tag", json={"label": "新分类"})
    assert r.status_code == 201
    value = r.json()["data"]["tag"]  # 服务端生成的内部 value
    r = admin_client.get("/api/admin/tags")
    assert r.status_code == 200
    by_val = {t["value"]: t for t in r.json()["tags"]}
    assert by_val[value]["label"] == "新分类"
    assert by_val[value]["enabled"] is False
    assert by_val[value]["pending"]["vote_count"] >= 1
    assert "vote_threshold" in r.json()


def test_tags_approve_enables(admin_client):
    bid = _make_barrage("active", "t", "00")
    r = admin_client.post(f"/api/barrage/{bid}/propose-tag", json={"label": "L"})
    value = r.json()["data"]["tag"]
    r = admin_client.post(f"/api/admin/tags/{value}/approve")
    assert r.status_code == 200
    with _db.SessionLocal() as s:
        assert s.get(Tag, value).enabled is True


# ---- pending --------------------------------------------------------------


def test_pending_list_and_approve(admin_client):
    bid = _make_barrage("pending", "待审 A")
    r = admin_client.get("/api/admin/pending")
    assert r.status_code == 200
    assert any(it["content"] == "待审 A" for it in r.json()["items"])

    r = admin_client.post(f"/api/admin/pending/{bid}/approve", json={"tags": "00,02"})
    assert r.status_code == 200
    with _db.SessionLocal() as s:
        row = s.get(Barrage, bid)
        assert row.status == "active" and row.tags == "00,02"


def test_pending_reject(admin_client):
    bid = _make_barrage("pending", "reject me")
    r = admin_client.post(f"/api/admin/pending/{bid}/reject")
    assert r.status_code == 200
    with _db.SessionLocal() as s:
        assert s.get(Barrage, bid).status == "deleted"


# ---- reports --------------------------------------------------------------


def test_reports_lists_reported_only_and_dismiss(admin_client):
    _make_barrage("active", "无反馈")
    dirty = _make_barrage("active", "被反馈")
    with _db.SessionLocal() as s:
        s.get(Barrage, dirty).report_cnt = 3
        s.add(BarrageReport(barrage_id=dirty, ip_hash="hashx", ts=datetime.utcnow()))
        s.commit()
    r = admin_client.get("/api/admin/reports")
    assert r.status_code == 200
    contents = {it["content"] for it in r.json()["items"]}
    assert "被反馈" in contents and "无反馈" not in contents

    r = admin_client.post(f"/api/admin/reports/{dirty}/dismiss")
    assert r.status_code == 200
    with _db.SessionLocal() as s:
        assert s.get(Barrage, dirty).report_cnt == 0
        assert s.execute(
            select(BarrageReport).where(BarrageReport.barrage_id == dirty)
        ).scalars().all() == []


# ---- trash ----------------------------------------------------------------


def test_trash_restore(admin_client):
    bid = _make_barrage("deleted", "trashed")
    r = admin_client.post(f"/api/admin/trash/{bid}/restore")
    assert r.status_code == 200
    with _db.SessionLocal() as s:
        assert s.get(Barrage, bid).status == "active"


def test_trash_purge(admin_client):
    bid = _make_barrage("deleted", "to-purge")
    with _db.SessionLocal() as s:
        s.add(BarrageReport(barrage_id=bid, ip_hash="h", ts=datetime.utcnow()))
        s.commit()
    r = admin_client.post(f"/api/admin/trash/{bid}/purge")
    assert r.status_code == 200
    with _db.SessionLocal() as s:
        assert s.get(Barrage, bid) is None


# ---- live_hot -------------------------------------------------------------


def test_live_hot_list_and_filtered(admin_client):
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        s.execute(insert(DailyHot).values(
            live_date=_current_live_date_iso(), content_norm="加一", content_sample="加一",
            first_seen=now - timedelta(hours=1), last_seen=now,
            send_cnt=10, unique_sender_cnt=5, is_filtered=False,
        ))
        s.commit()
    r = admin_client.get("/api/admin/live-hot")
    assert r.status_code == 200
    assert any(it["content_sample"] == "加一" for it in r.json()["items"])
    # filtered 视图不含未过滤行
    r = admin_client.get("/api/admin/live-hot?filtered=true")
    assert r.status_code == 200
    assert all(it["content_sample"] != "加一" for it in r.json()["items"])


def test_live_hot_detail(admin_client):
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        res = s.execute(insert(DailyHot).values(
            live_date=_current_live_date_iso(), content_norm="abc", content_sample="abc",
            first_seen=now, last_seen=now, send_cnt=3, unique_sender_cnt=2, is_filtered=False,
        ))
        hid = res.inserted_primary_key[0]
        s.execute(insert(RawDanmaku).values(ts=now, uid="u1", nickname="n1",
                                            content_raw="abc", content_norm="abc"))
        s.execute(insert(RawDanmaku).values(ts=now, uid="u1", nickname="n1",
                                            content_raw="abc", content_norm="abc"))
        s.commit()
    r = admin_client.get(f"/api/admin/live-hot/{hid}")
    assert r.status_code == 200
    body = r.json()
    assert body["hot"]["content_sample"] == "abc"
    assert len(body["raws"]) == 2
    assert body["top_uids"][0] == {"uid": "u1", "count": 2}


def test_live_hot_detail_404(admin_client):
    assert admin_client.get("/api/admin/live-hot/999999").status_code == 404


def test_live_hot_rescan(admin_client):
    r = admin_client.post("/api/admin/live-hot/rescan")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_live_hot_recompute(admin_client):
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        s.execute(insert(RawDanmaku).values(ts=now, uid="u1", nickname="t",
                                            content_raw="奇怪内容", content_norm="奇怪内容"))
        s.commit()
    r = admin_client.post("/api/admin/live-hot/recompute")
    assert r.status_code == 200 and "raw_renormalized" in r.json()


# ---- stats ----------------------------------------------------------------


def test_stats_shape(admin_client):
    _make_barrage("pending", "p1")
    _make_barrage("deleted", "d1")
    r = admin_client.get("/api/admin/stats")
    assert r.status_code == 200
    body = r.json()
    for k in ("raw_24h", "submit_24h", "copy_total", "live_hot_total",
              "pending_total", "deleted_total", "report_24h", "top_ip"):
        assert k in body
    assert body["pending_total"] >= 1 and body["deleted_total"] >= 1
