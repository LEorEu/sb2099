"""公开页 SSR：/ / /barrage / /live / /userscript 状态码与 HTML 关键文本。"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import insert

from sb2099 import db as _db
from sb2099.models import Barrage, LiveHot


@pytest.fixture
def client(tmp_db):
    from sb2099.web.routes_api import router as api_router
    from sb2099.web.routes_public import router as public_router

    app = FastAPI()
    app.include_router(api_router)
    app.include_router(public_router)
    static_dir = Path(__file__).parent.parent / "sb2099" / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    return TestClient(app)


def test_home_200(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "sb2099" in r.text
    assert "12740109" in r.text


def test_barrage_page_empty(client):
    r = client.get("/barrage")
    assert r.status_code == 200
    assert "暂无投稿" in r.text


def test_barrage_page_with_data(client):
    with _db.SessionLocal() as s:
        s.execute(
            insert(Barrage).values(
                content="测试烂梗 ABC",
                content_norm="测试烂梗 abc",
                tags="00,02",
                source="user",
                submit_time=datetime.utcnow(),
                cnt=5,
                status="active",
            )
        )
        s.commit()
    r = client.get("/barrage")
    assert r.status_code == 200
    assert "测试烂梗 ABC" in r.text
    assert "复制 5" in r.text


def test_live_page_empty(client):
    r = client.get("/live")
    assert r.status_code == 200
    assert "暂无热门弹幕" in r.text


def test_live_page_with_data(client):
    now = datetime.utcnow()
    with _db.SessionLocal() as s:
        s.execute(
            insert(LiveHot).values(
                content_norm="加一",
                content_sample="加一",
                first_seen=now - timedelta(hours=1),
                last_seen=now,
                send_cnt_24h=42,
                unique_sender_cnt_24h=20,
                send_cnt_total=42,
                is_filtered=False,
            )
        )
        s.commit()
    r = client.get("/live?window=day")
    assert r.status_code == 200
    assert "加一" in r.text
    assert "×42" in r.text


def test_userscript_served(client):
    r = client.get("/userscript")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert "==UserScript==" in r.text
