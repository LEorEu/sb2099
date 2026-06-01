"""公开页：/userscript 状态码与内容验证。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_db):
    from tests.conftest import build_test_app
    from sb2099.ratelimit import limiter
    limiter.reset()
    return TestClient(build_test_app())


def test_userscript_served(client):
    r = client.get("/userscript")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert "==UserScript==" in r.text
