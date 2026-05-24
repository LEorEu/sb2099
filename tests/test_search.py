"""search.search_barrage: FTS5 全文 + tag CSV 多选 + 排序 + status active 过滤。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import insert

from sb2099 import db as _db
from sb2099.models import Barrage
from sb2099.search import search_barrage


@pytest.fixture
def seed_barrage(tmp_db):
    """灌 5 条 active + 1 条 pending + 1 条 deleted。"""
    now = datetime.utcnow()
    rows = [
        # active
        ("草", "草", "00", "active", now - timedelta(minutes=1), 10),
        ("加一", "加一", "02", "active", now - timedelta(minutes=2), 50),
        ("打 rl", "打 rl", "01", "active", now - timedelta(minutes=3), 3),
        ("好的", "好的", "02,99", "active", now - timedelta(minutes=4), 8),
        ("草草草", "草草草", "00", "active", now - timedelta(minutes=5), 100),
        # 非 active
        ("待审", "待审", "99", "pending", now - timedelta(minutes=6), 0),
        ("删除", "删除", "99", "deleted", now - timedelta(minutes=7), 0),
    ]
    with _db.SessionLocal() as s:
        for content, cn, tags, status, t, cnt in rows:
            s.execute(
                insert(Barrage).values(
                    content=content,
                    content_norm=cn,
                    tags=tags,
                    source="user",
                    submit_time=t,
                    cnt=cnt,
                    status=status,
                )
            )
        s.commit()


def test_default_returns_only_active(seed_barrage):
    r = search_barrage()
    assert r["total"] == 5
    contents = {row["content"] for row in r["list"]}
    assert "待审" not in contents and "删除" not in contents


def test_sort_new_orders_by_submit_time_desc(seed_barrage):
    r = search_barrage(sort="new", size=10)
    contents = [row["content"] for row in r["list"]]
    assert contents == ["草", "加一", "打 rl", "好的", "草草草"]


def test_sort_hot_orders_by_cnt_desc(seed_barrage):
    r = search_barrage(sort="hot", size=10)
    contents = [row["content"] for row in r["list"]]
    assert contents == ["草草草", "加一", "草", "好的", "打 rl"]


def test_tag_filter_single(seed_barrage):
    r = search_barrage(tags=["02"], size=10)
    contents = {row["content"] for row in r["list"]}
    assert contents == {"加一", "好的"}


def test_tag_filter_multi_or(seed_barrage):
    """tag=01,99 → 任一匹配。"""
    r = search_barrage(tags=["01", "99"], size=10)
    contents = {row["content"] for row in r["list"]}
    assert contents == {"打 rl", "好的"}


def test_fts5_match(seed_barrage):
    r = search_barrage(q="草", size=10)
    contents = {row["content"] for row in r["list"]}
    # FTS5 unicode61 应当能匹配中文字符 "草"，命中含该字的两条
    assert "草" in contents
    assert "草草草" in contents


def test_pagination_last_page(seed_barrage):
    r = search_barrage(size=3, page=1)
    assert len(r["list"]) == 3
    assert r["last_page"] is False
    r2 = search_barrage(size=3, page=2)
    assert len(r2["list"]) == 2
    assert r2["last_page"] is True


def test_empty_query_with_tag(seed_barrage):
    r = search_barrage(q="", tags=["00"], size=10)
    contents = {row["content"] for row in r["list"]}
    assert contents == {"草", "草草草"}
