"""/api/* 只读路由：tags / live / barrage / random / userscript/version。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, update

from sb2099 import db as _db
from sb2099.models import Barrage, LiveHot


@pytest.fixture
def client(tmp_db):
    # 避免 lifespan 拉起 ingest/cron 真连 VPS WS — 直接构 ASGI app 但 lifespan="off"
    from sb2099.web.routes_api import router as api_router
    from sb2099.web.routes_public import router as public_router
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from pathlib import Path

    app = FastAPI()
    app.include_router(api_router)
    app.include_router(public_router)
    static_dir = Path(__file__).parent.parent / "sb2099" / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    return TestClient(app)


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
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        for i in range(15):
            s.execute(
                insert(LiveHot).values(
                    content_norm=f"cn{i}",
                    content_sample=f"sample{i}",
                    first_seen=now - timedelta(minutes=i),
                    last_seen=now - timedelta(minutes=i),
                    send_cnt_24h=100 - i,
                    send_cnt_7d=100 - i,
                    send_cnt_total=100 - i,
                    unique_sender_cnt_24h=50 - i,
                    is_filtered=(i == 0),  # 把 top1 标 filtered
                )
            )
        s.commit()

    r = client.get("/api/live?window=day")
    data = r.json()["data"]
    assert len(data) == 10
    # is_filtered=1 的 cn0 应被排除
    assert all(d["content_sample"] != "sample0" for d in data)
    # 按 send_cnt_24h desc 排序
    assert data[0]["content_sample"] == "sample1"
    assert data[0]["send_cnt"] == 99


def test_live_week_limit_50(client):
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        for i in range(60):
            s.execute(
                insert(LiveHot).values(
                    content_norm=f"x{i}",
                    content_sample=f"x{i}",
                    first_seen=now,
                    last_seen=now,
                    send_cnt_7d=100 - i,
                    send_cnt_total=100,
                )
            )
        s.commit()
    r = client.get("/api/live?window=week")
    assert len(r.json()["data"]) == 50


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
