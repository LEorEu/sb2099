"""共用 fixture：临时 sqlite + alembic upgrade head + 测试 app 工厂。"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def build_test_app():
    """与生产 app 同构但不挂 lifespan（避免 ingest/cron 真连上游 WS）。"""
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    from sb2099.ratelimit import limiter
    from sb2099.web.routes_api import router as api_router
    from sb2099.web.routes_public import router as public_router

    app = FastAPI()
    app.state.limiter = limiter

    from fastapi.responses import JSONResponse

    def _rate_limit_handler(request, exc):  # noqa: ANN001
        return JSONResponse(
            status_code=429, content={"detail": f"rate limit exceeded: {exc.detail}"}
        )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(api_router)
    app.include_router(public_router)
    static_dir = Path(__file__).parent.parent / "sb2099" / "web" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    return app


@pytest.fixture()
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """每个用例一个独立的 sqlite，alembic 0001 灌入种子数据。

    必须在导入 sb2099.db 之前设置环境变量（db.py 在 import 时建 engine）。
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SB2099_ADMIN_TOKEN", "test_token_" + "x" * 16)
    monkeypatch.setenv("SB2099_IP_SALT", "test_salt_" + "x" * 8)
    monkeypatch.setenv("SB2099_DB_PATH", str(db_path))
    monkeypatch.setenv("DOUYU_LIVE_WS_URL", "ws://127.0.0.1:1/none")

    # 清掉可能已 cache 的 settings 单例
    from sb2099 import config as _cfg
    _cfg.get_settings.cache_clear()

    # 重建 db engine 指到 tmp_path
    import sb2099.db as _db
    from sqlalchemy import create_engine, event

    engine = create_engine(
        _cfg.get_settings().db_url,
        connect_args={"check_same_thread": False, "timeout": 30},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_wal(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    from sqlalchemy.orm import sessionmaker
    _db.engine = engine
    _db.SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

    # 跑 alembic
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parent.parent / "alembic"))
    command.upgrade(cfg, "head")

    # 重置 settings_cache 单例
    from sb2099 import settings as _set
    _set.settings_cache.invalidate()

    yield db_path

    engine.dispose()
