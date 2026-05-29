"""/admin/* 路由：登录、鉴权 gate、settings 改写、tags CRUD、pending 审核、回收站等。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from sb2099 import db as _db
from sb2099.models import Barrage, BarrageReport, DailyHot, RawDanmaku, Setting, Tag
from sb2099.web.admin_auth import COOKIE_NAME


ADMIN_TOKEN = "test_token_" + "x" * 16  # 与 conftest 中 monkeypatch 的一致


@pytest.fixture
def client(tmp_db):
    from tests.conftest import build_test_app
    from sb2099.ratelimit import limiter
    limiter.reset()
    return TestClient(build_test_app(), follow_redirects=False)


@pytest.fixture
def admin_client(client):
    r = client.post("/admin/login", data={"token": ADMIN_TOKEN, "next": "/admin/settings"})
    assert r.status_code == 303
    assert COOKIE_NAME in r.cookies or "sb2099_admin" in client.cookies
    return client


# ---- auth -----------------------------------------------------------------


def test_login_get_renders_form(client):
    r = client.get("/admin/login")
    assert r.status_code == 200
    assert "SB2099_ADMIN_TOKEN" in r.text


def test_login_wrong_token(client):
    r = client.post("/admin/login", data={"token": "wrong"})
    assert r.status_code == 303
    assert "err=1" in r.headers["location"]


def test_login_correct_sets_cookie(client):
    r = client.post(
        "/admin/login", data={"token": ADMIN_TOKEN, "next": "/admin/settings"}
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/settings"
    # cookie 设置
    set_cookie = r.headers.get("set-cookie", "")
    assert "sb2099_admin=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie.lower() or "samesite=strict" in set_cookie.lower()


def test_protected_page_redirects_when_logged_out(client):
    r = client.get("/admin/settings")
    assert r.status_code == 307
    assert r.headers["location"] == "/admin/login"


def test_protected_post_returns_401_when_logged_out(client):
    r = client.post("/admin/settings", data={})
    assert r.status_code == 401


def test_logout_clears_cookie(admin_client):
    r = admin_client.post("/admin/logout")
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


# ---- settings -------------------------------------------------------------


def test_settings_page_lists_defaults(admin_client):
    r = admin_client.get("/admin/settings")
    assert r.status_code == 200
    assert "live_noise_filters" in r.text
    assert "submission_review_rules" in r.text


def test_settings_update_writes_db_and_invalidates_cache(admin_client):
    from sb2099.settings import settings_cache

    # lines 类型:每行一条,前后空白和空行自动清理
    new_filters_text = "晚安\n  好梦  \n\n"
    r = admin_client.post(
        "/admin/settings",
        data={"live_noise_filters": new_filters_text, "barrage_max_length": "500"},
    )
    assert r.status_code == 303
    assert "ok=1" in r.headers["location"]
    # 立即读 settings_cache(应已 invalidate → 重载)
    assert settings_cache.get("live_noise_filters") == ["晚安", "好梦"]
    assert settings_cache.get("barrage_max_length") == 500


def test_settings_int_field_rejects_non_integer(admin_client):
    r = admin_client.post(
        "/admin/settings",
        data={"barrage_max_length": "not-a-number"},
    )
    assert r.status_code == 303
    assert "err=" in r.headers["location"]


def test_settings_lines_field_accepts_empty(admin_client):
    """清空降噪关键词应当合法,落库成空数组。"""
    from sb2099.settings import settings_cache

    r = admin_client.post(
        "/admin/settings",
        data={"live_noise_filters": ""},
    )
    assert r.status_code == 303
    assert "ok=1" in r.headers["location"]
    assert settings_cache.get("live_noise_filters") == []


# ---- tags CRUD ------------------------------------------------------------


def test_tags_create_update_delete(admin_client):
    # create
    r = admin_client.post(
        "/admin/tags",
        data={"value": "08", "label": "新 tag", "icon_url": "", "sort": "5"},
    )
    assert r.status_code == 303
    with _db.SessionLocal() as s:
        row = s.get(Tag, "08")
        assert row and row.label == "新 tag"

    # update
    r = admin_client.post(
        "/admin/tags/08/update",
        data={"label": "改了", "icon_url": "https://x/y.png", "sort": "9", "enabled": "0"},
    )
    assert r.status_code == 303
    with _db.SessionLocal() as s:
        row = s.get(Tag, "08")
        assert row.label == "改了"
        assert row.icon_url == "https://x/y.png"
        assert row.enabled is False

    # delete
    r = admin_client.post("/admin/tags/08/delete")
    assert r.status_code == 303
    with _db.SessionLocal() as s:
        assert s.get(Tag, "08") is None


def test_tags_page_renders_pending_section(admin_client):
    """有候选 tag 时 /admin/tags 页面应渲染"观众提议待审"区块。"""
    from datetime import datetime
    from sb2099.models import Barrage
    with _db.SessionLocal() as s:
        b = Barrage(content="t", content_norm="t", tags="00", source="user",
                    submit_time=datetime.utcnow(), status="active")
        s.add(b)
        s.commit()
        bid = b.id
    r = admin_client.post(f"/api/barrage/{bid}/propose-tag",
                          json={"value": "abc", "label": "新分类"})
    assert r.status_code == 201
    r = admin_client.get("/admin/tags")
    assert r.status_code == 200
    assert "观众提议待审" in r.text
    assert "abc" in r.text
    assert "新分类" in r.text


def test_tags_create_bad_value_rejected(admin_client):
    r = admin_client.post(
        "/admin/tags",
        data={"value": "bad value with space", "label": "x"},
    )
    assert r.status_code == 400


def test_tags_create_duplicate_409(admin_client):
    r = admin_client.post("/admin/tags", data={"value": "00", "label": "重复"})
    assert r.status_code == 409


# ---- pending / approve / reject ------------------------------------------


def _make_barrage(status: str = "pending", content: str = "test", tags: str = "00") -> int:
    with _db.SessionLocal() as s:
        b = Barrage(
            content=content,
            content_norm=content,
            tags=tags,
            source="user",
            submit_time=datetime.utcnow(),
            status=status,
        )
        s.add(b)
        s.commit()
        return b.id


def test_pending_listed(admin_client):
    _make_barrage("pending", "待审条目 A")
    r = admin_client.get("/admin/barrage/pending")
    assert r.status_code == 200
    assert "待审条目 A" in r.text


def test_approve_flips_to_active(admin_client):
    bid = _make_barrage("pending", "approve me")
    r = admin_client.post(
        f"/admin/barrage/{bid}/approve", data={"tags": "00,02"}
    )
    assert r.status_code == 303
    with _db.SessionLocal() as s:
        row = s.get(Barrage, bid)
        assert row.status == "active"
        assert row.tags == "00,02"


def test_reject_flips_to_deleted(admin_client):
    bid = _make_barrage("pending", "reject me")
    r = admin_client.post(f"/admin/barrage/{bid}/reject")
    assert r.status_code == 303
    with _db.SessionLocal() as s:
        assert s.get(Barrage, bid).status == "deleted"


# ---- reports --------------------------------------------------------------


def test_reports_lists_reported_only(admin_client):
    bid_clean = _make_barrage("active", "无反馈")
    bid_dirty = _make_barrage("active", "被反馈")
    with _db.SessionLocal() as s:
        b = s.get(Barrage, bid_dirty)
        b.report_cnt = 3
        s.add(BarrageReport(barrage_id=bid_dirty, ip_hash="hashx", ts=datetime.utcnow()))
        s.commit()
    r = admin_client.get("/admin/barrage/reports")
    assert r.status_code == 200
    assert "被反馈" in r.text
    assert "无反馈" not in r.text


# ---- trash ---------------------------------------------------------------


def test_trash_restore(admin_client):
    bid = _make_barrage("deleted", "trashed")
    r = admin_client.post(f"/admin/barrage/{bid}/restore")
    assert r.status_code == 303
    with _db.SessionLocal() as s:
        assert s.get(Barrage, bid).status == "active"


def test_trash_purge_removes_row(admin_client):
    bid = _make_barrage("deleted", "to-purge")
    with _db.SessionLocal() as s:
        s.add(BarrageReport(barrage_id=bid, ip_hash="h", ts=datetime.utcnow()))
        s.commit()
    r = admin_client.post(f"/admin/barrage/{bid}/purge")
    assert r.status_code == 303
    with _db.SessionLocal() as s:
        assert s.get(Barrage, bid) is None
        reps = s.execute(
            select(BarrageReport).where(BarrageReport.barrage_id == bid)
        ).scalars().all()
        assert reps == []


# ---- live_hot list / detail / rescan -------------------------------------


def _current_live_date_iso():
    from datetime import timezone
    from sb2099.live_day import current_live_window

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ld, _ = current_live_window(now)
    return ld.isoformat()


def test_live_hot_listing(admin_client):
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        s.execute(
            insert(DailyHot).values(
                live_date=_current_live_date_iso(),
                content_norm="加一",
                content_sample="加一",
                first_seen=now - timedelta(hours=1),
                last_seen=now,
                send_cnt=10,
                unique_sender_cnt=5,
                is_filtered=False,
            )
        )
        s.commit()
    r = admin_client.get("/admin/live_hot")
    assert r.status_code == 200
    assert "加一" in r.text


def test_live_hot_filtered_toggle(admin_client):
    now = datetime.utcnow()
    ld = _current_live_date_iso()
    with _db.SessionLocal() as s:
        s.execute(
            insert(DailyHot).values(
                live_date=ld,
                content_norm="clean",
                content_sample="clean",
                first_seen=now,
                last_seen=now,
                send_cnt=5,
                unique_sender_cnt=5,
                is_filtered=False,
            )
        )
        s.commit()
    # daily_hot 通常没有 filtered 行；只断言 filtered 视图可正常打开，
    # 且未过滤的种子行不会出现在 filtered=true 视图。
    r = admin_client.get("/admin/live_hot?filtered=true")
    assert r.status_code == 200
    assert "clean" not in r.text


def test_live_hot_rescan_recomputes(admin_client):
    """rescan 现在只触发一次 recount，返回 303 重定向，页面可达。"""
    from sb2099.settings import settings_cache

    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        s.execute(
            insert(RawDanmaku).values(
                ts=now,
                uid="u1",
                nickname="t",
                content_raw="奇怪内容",
                content_norm="奇怪内容",
            )
        )
        s.commit()
    settings_cache.invalidate()

    r = admin_client.post("/admin/live_hot/rescan")
    assert r.status_code == 303
    # 重定向目标页面应可正常打开
    page = admin_client.get("/admin/live_hot")
    assert page.status_code == 200


def test_live_hot_detail_lists_raw_and_top_uids(admin_client):
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        res = s.execute(
            insert(DailyHot).values(
                live_date=_current_live_date_iso(),
                content_norm="刷子",
                content_sample="刷子",
                first_seen=now,
                last_seen=now,
                send_cnt=3,
                unique_sender_cnt=2,
                is_filtered=False,
            )
        )
        hid = res.inserted_primary_key[0]
        # 3 条 raw，uid 重复
        for i in range(3):
            s.execute(
                insert(RawDanmaku).values(
                    ts=now,
                    uid="u1" if i < 2 else "u2",
                    nickname="x",
                    content_raw="刷子",
                    content_norm="刷子",
                )
            )
        s.commit()
    r = admin_client.get(f"/admin/live_hot/{hid}")
    assert r.status_code == 200
    assert "u1" in r.text
    assert "u2" in r.text


# ---- stats ----------------------------------------------------------------


def test_stats_renders(admin_client):
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        s.execute(
            insert(Barrage).values(
                content="x",
                content_norm="x",
                tags="00",
                source="user",
                submitter_ip_hash="hashAAA",
                submit_time=now,
                cnt=3,
                status="active",
            )
        )
        s.commit()
    r = admin_client.get("/admin/stats")
    assert r.status_code == 200
    assert "hashAAA" in r.text
    assert "24h 新增投稿" in r.text
