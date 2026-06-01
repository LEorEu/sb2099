"""/api/live 每项含 in_library：content_norm 命中 active barrage 即 True。"""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def test_live_marks_in_library(tmp_db):
    from sqlalchemy import insert

    from sb2099 import db as _db
    from sb2099.live_day import current_live_window
    from sb2099.models import Barrage, DailyHot
    from sb2099.ratelimit import limiter
    from tests.conftest import build_test_app

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    live_date, _ = current_live_window(now)
    with _db.SessionLocal() as s:
        s.execute(insert(DailyHot).values(
            live_date=live_date.isoformat(), content_norm="已入库样本", content_sample="已入库样本",
            first_seen=now - timedelta(hours=1), last_seen=now,
            send_cnt=50, unique_sender_cnt=20, is_filtered=False))
        s.execute(insert(DailyHot).values(
            live_date=live_date.isoformat(), content_norm="未入库样本", content_sample="未入库样本",
            first_seen=now - timedelta(hours=1), last_seen=now,
            send_cnt=30, unique_sender_cnt=10, is_filtered=False))
        s.execute(insert(Barrage).values(
            content="已入库样本", content_norm="已入库样本", tags="00", source="user",
            submit_time=now, cnt=0, status="active"))
        s.commit()

    limiter.reset()
    client = TestClient(build_test_app())
    r = client.get("/api/live?window=day")
    assert r.status_code == 200
    data = r.json()["data"]
    by_in = {it["content_sample"]: it["in_library"] for it in data}
    assert by_in["已入库样本"] is True
    assert by_in["未入库样本"] is False
