"""SPA 回退：未知前端路径返回 index.html；/assets 可取；/api 不被吞。"""
from fastapi.testclient import TestClient


def test_spa_fallback_and_api_untouched(tmp_db, tmp_path):
    from tests.conftest import build_test_app
    from sb2099.ratelimit import limiter

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=app>SPA</div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")

    limiter.reset()
    client = TestClient(build_test_app(dist_dir=dist))

    # 未知前端路由 → index.html
    r = client.get("/barrage")
    assert r.status_code == 200
    assert "SPA" in r.text

    # 资源可取
    r2 = client.get("/assets/app.js")
    assert r2.status_code == 200

    # /api 仍是 JSON，不被回退吞掉
    r3 = client.get("/api/tags")
    assert r3.status_code == 200
    assert r3.headers["content-type"].startswith("application/json")
