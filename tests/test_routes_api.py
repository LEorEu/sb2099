"""/api/* 只读路由：tags / live / barrage / random / userscript/version。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, update

from sb2099 import db as _db
from sb2099.models import Barrage, DailyHot


def _seed_daily(content_sample, content_norm=None, *, live_date=None,
                send_cnt=10, unique=5, page_copy_cnt=0, is_filtered=False):
    """在「当前数据日」种入一条 daily_hot，返回其 id。"""
    from datetime import datetime, timezone
    from sqlalchemy import insert as sa_insert, select as sa_select
    from sb2099.db import SessionLocal
    from sb2099.live_day import current_live_window
    from sb2099.normalize import normalize

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ld, _ = current_live_window(now)
    cn = content_norm or normalize(content_sample)
    with SessionLocal() as s:
        s.execute(sa_insert(DailyHot).values(
            live_date=(live_date or ld.isoformat()),
            content_norm=cn, content_sample=content_sample,
            send_cnt=send_cnt, unique_sender_cnt=unique,
            first_seen=now, last_seen=now,
            page_copy_cnt=page_copy_cnt, is_filtered=is_filtered,
        ))
        s.commit()
        return s.execute(
            sa_select(DailyHot.id).where(DailyHot.content_norm == cn)
        ).scalars().first()


@pytest.fixture
def client(tmp_db):
    from tests.conftest import build_test_app

    # 限流计数器是 Limiter 实例上的 in-memory storage；
    # 用例之间需重置避免相互污染
    from sb2099.ratelimit import limiter
    limiter.reset()
    return TestClient(build_test_app())


def test_tags_returns_initial_four(client):
    r = client.get("/api/tags")
    assert r.status_code == 200
    data = r.json()["data"]
    values = [t["value"] for t in data]
    assert values == ["00", "01", "02", "99"]


def test_live_empty(client):
    r = client.get("/api/live?window=day")
    assert r.status_code == 200
    body = r.json()
    assert body["window"] == "day"
    assert body["data"] == []


def test_live_day_filters_out_is_filtered_and_limits_to_10(client):
    for i in range(15):
        _seed_daily(
            f"sample{i}", content_norm=f"cn{i}",
            send_cnt=100 - i, unique=50 - i,
            is_filtered=(i == 0),  # 把 top1 标 filtered
        )

    r = client.get("/api/live?window=day")
    data = r.json()["data"]
    assert len(data) == 10
    # is_filtered=1 的 cn0 应被排除
    assert all(d["content_sample"] != "sample0" for d in data)
    # 按 send_cnt desc 排序
    assert data[0]["content_sample"] == "sample1"
    assert data[0]["send_cnt"] == 99


def test_live_week_aggregates_across_days(client):
    from datetime import datetime, timezone
    from sb2099.live_day import current_live_window

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today, _ = current_live_window(now)
    six_days_ago = (today - timedelta(days=6)).isoformat()

    _seed_daily("今天的梗", content_norm="today_cn", send_cnt=10)
    _seed_daily("六天前的梗", content_norm="old_cn", send_cnt=20, live_date=six_days_ago)

    r = client.get("/api/live?window=week")
    data = r.json()["data"]
    samples = [d["content_sample"] for d in data]
    assert "今天的梗" in samples
    assert "六天前的梗" in samples


def test_barrage_empty(client):
    r = client.get("/api/barrage")
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["list"] == []
    assert body["total"] == 0


def test_random_empty_returns_404(client):
    r = client.get("/api/random")
    assert r.status_code == 404


def test_random_returns_one(client):
    with _db.SessionLocal() as s:
        s.execute(
            insert(Barrage).values(
                content="hi",
                content_norm="hi",
                tags="00",
                source="user",
                submit_time=datetime.utcnow(),
                cnt=0,
                status="active",
            )
        )
        s.commit()
    r = client.get("/api/random")
    assert r.status_code == 200
    assert r.json()["data"]["content"] == "hi"


def test_userscript_version(client):
    r = client.get("/api/userscript/version")
    assert r.status_code == 200
    assert "version" in r.json()


# ---- slice W: write endpoints -----------------------------------------------


def _seed_live_hot(content_sample="加一", content_norm=None):
    return _seed_daily(content_sample, content_norm, send_cnt=1, unique=5)


def test_submit_barrage_active(client):
    r = client.post("/api/barrage", json={"content": "好玩的烂梗一条", "tags": ["00"]})
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["status"] == "active"
    assert data["tags"] == "00"


def test_submit_barrage_dedup_409(client):
    r1 = client.post("/api/barrage", json={"content": "唯一内容ABC", "tags": ["00"]})
    assert r1.status_code == 201
    r2 = client.post("/api/barrage", json={"content": "唯一内容ABC", "tags": ["01"]})
    assert r2.status_code == 409
    body = r2.json()["detail"]
    assert body["message"] == "duplicate"
    assert body["existing"]["content"] == "唯一内容ABC"


def test_submit_barrage_block_422(client):
    """改 setting 加 block 规则 → POST 应 422 拒收。"""
    import json
    from datetime import datetime
    from sqlalchemy import update as sa_update
    from sb2099.models import Setting
    from sb2099.settings import settings_cache

    with _db.SessionLocal() as s:
        s.execute(
            sa_update(Setting)
            .where(Setting.key == "submission_review_rules")
            .values(
                value=json.dumps([{"type": "keyword", "pattern": "加微信", "action": "block"}]),
                updated_at=datetime.utcnow(),
            )
        )
        s.commit()
    settings_cache.invalidate()

    r = client.post("/api/barrage", json={"content": "加微信领奖品", "tags": ["00"]})
    assert r.status_code == 422
    assert r.json()["detail"]["message"] == "blocked"


def test_submit_barrage_pending(client):
    import json
    from datetime import datetime
    from sqlalchemy import update as sa_update
    from sb2099.models import Setting
    from sb2099.settings import settings_cache

    with _db.SessionLocal() as s:
        s.execute(
            sa_update(Setting)
            .where(Setting.key == "submission_review_rules")
            .values(
                value=json.dumps([{"type": "keyword", "pattern": "广告", "action": "pending"}]),
                updated_at=datetime.utcnow(),
            )
        )
        s.commit()
    settings_cache.invalidate()

    r = client.post("/api/barrage", json={"content": "测试广告内容", "tags": ["00"]})
    assert r.status_code == 201
    assert r.json()["data"]["status"] == "pending"


def test_submit_barrage_invalid_tag_400(client):
    r = client.post("/api/barrage", json={"content": "随便内容", "tags": ["XX"]})
    assert r.status_code == 400


def test_submit_barrage_short_content_400(client):
    r = client.post("/api/barrage", json={"content": "短", "tags": ["00"]})
    assert r.status_code == 400


def test_submit_barrage_rate_limit_429(client):
    """默认 5/h；第 6 次 → 429。"""
    for i in range(5):
        r = client.post(
            "/api/barrage",
            json={"content": f"内容编号{i:04d}测试", "tags": ["00"]},
        )
        assert r.status_code == 201, f"#{i} {r.text}"
    r6 = client.post("/api/barrage", json={"content": "第六条内容", "tags": ["00"]})
    assert r6.status_code == 429


def test_copy_barrage_increments(client):
    from sb2099.models import Barrage as _B
    from datetime import datetime
    from sqlalchemy import select as sa_select
    with _db.SessionLocal() as s:
        b = _B(
            content="可复制",
            content_norm="可复制",
            tags="00",
            source="user",
            submit_time=datetime.utcnow(),
            cnt=0,
            status="active",
        )
        s.add(b)
        s.commit()
        bid = b.id
    r = client.post("/api/copy", json={"source": "barrage", "id": bid})
    assert r.status_code == 200
    with _db.SessionLocal() as s:
        cnt = s.execute(sa_select(_B.cnt).where(_B.id == bid)).scalar_one()
        assert cnt == 1


def test_copy_live_hot_increments(client):
    hid = _seed_live_hot("某复读")
    r = client.post("/api/copy", json={"source": "live_hot", "id": hid})
    assert r.status_code == 200
    from sqlalchemy import select as sa_select
    from sb2099.models import DailyHot
    with _db.SessionLocal() as s:
        cnt = s.execute(
            sa_select(DailyHot.page_copy_cnt).where(DailyHot.id == hid)
        ).scalar_one()
        assert cnt == 1


def test_copy_404(client):
    r = client.post("/api/copy", json={"source": "barrage", "id": 999999})
    assert r.status_code == 404


def test_report_uniqueness_per_ip(client):
    from datetime import datetime
    from sb2099.models import Barrage as _B
    with _db.SessionLocal() as s:
        b = _B(
            content="可举报",
            content_norm="可举报",
            tags="00",
            source="user",
            submit_time=datetime.utcnow(),
            status="active",
        )
        s.add(b)
        s.commit()
        bid = b.id
    r1 = client.post("/api/barrage/report", json={"id": bid})
    assert r1.status_code == 200
    assert r1.json()["data"]["report_cnt"] == 1
    # 同 IP 第二次：应当被 UNIQUE 约束兜住，cnt 不增
    r2 = client.post("/api/barrage/report", json={"id": bid})
    assert r2.status_code == 200
    assert r2.json()["data"]["report_cnt"] == 1
    assert r2.json()["data"].get("duplicate") is True


def test_promote_creates_barrage_with_source_promoted(client):
    hid = _seed_live_hot("能提升的复读")
    r = client.post("/api/promote", json={"live_hot_id": hid, "tags": ["00"]})
    assert r.status_code == 201
    from sqlalchemy import select as sa_select
    from sb2099.models import Barrage as _B
    with _db.SessionLocal() as s:
        rows = s.execute(sa_select(_B.content, _B.source)).all()
        assert ("能提升的复读", "promoted") in [(r.content, r.source) for r in rows]


def test_promote_already_in_barrage_409(client):
    """live_hot 内容已在 barrage 表 → 409 不再入库（保留原热门行）。"""
    from datetime import datetime
    from sb2099.models import Barrage as _B
    with _db.SessionLocal() as s:
        s.add(_B(content="C", content_norm="C", tags="00", source="user",
                submit_time=datetime.utcnow(), status="active"))
        s.commit()
    hid = _seed_live_hot("C")
    r = client.post("/api/promote", json={"live_hot_id": hid, "tags": ["00"]})
    assert r.status_code == 409


def test_live_week_sums_same_content_across_days(client):
    from datetime import datetime, timedelta, timezone
    from sb2099.live_day import current_live_window
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today, _ = current_live_window(now)
    earlier = (today - timedelta(days=3)).isoformat()
    # 同一 content_norm 跨两个数据日，各 send_cnt=7 和 5 → 周榜应聚合为 12
    _seed_daily("跨天梗", content_norm="跨天梗", live_date=today.isoformat(), send_cnt=7, unique=5)
    _seed_daily("跨天梗", content_norm="跨天梗", live_date=earlier, send_cnt=5, unique=4)
    r = client.get("/api/live?window=week")
    assert r.status_code == 200
    rows = [d for d in r.json()["data"] if d["content_sample"] == "跨天梗"]
    assert len(rows) == 1
    assert rows[0]["send_cnt"] == 12


# ---- barrage/by-ids -------------------------------------------------------


def _seed_barrage(content, *, status="active", tags="00"):
    from sb2099.models import Barrage as _B
    with _db.SessionLocal() as s:
        b = _B(content=content, content_norm=content, tags=tags, source="user",
               submit_time=datetime.utcnow(), cnt=0, status=status)
        s.add(b)
        s.commit()
        return b.id


def test_by_ids_returns_active_in_request_order(client):
    a = _seed_barrage("第一条")
    b = _seed_barrage("第二条")
    r = client.get(f"/api/barrage/by-ids?ids={b},{a}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert [d["content"] for d in data] == ["第二条", "第一条"]


def test_by_ids_drops_inactive_and_missing(client):
    a = _seed_barrage("在库")
    gone = _seed_barrage("已删", status="deleted")
    r = client.get(f"/api/barrage/by-ids?ids={a},{gone},999999")
    assert r.status_code == 200
    assert [d["id"] for d in r.json()["data"]] == [a]


def test_by_ids_empty_param(client):
    r = client.get("/api/barrage/by-ids?ids=")
    assert r.status_code == 200
    assert r.json()["data"] == []
