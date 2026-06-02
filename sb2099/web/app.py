"""FastAPI 实例 + lifespan：startup 拉起 ingest worker + cron，shutdown 取消。"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from ..cron import archive_loop, recount_loop
from ..ingest.worker import start_background
from ..ratelimit import limiter
from .routes_api import router as api_router
from .routes_api_admin import router as api_admin_router
from .routes_public import router as public_router
from .spa import mount_spa

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sb2099")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ingest_task = start_background()
    recount_task = asyncio.create_task(recount_loop(), name="sb2099-recount")
    archive_task = asyncio.create_task(archive_loop(), name="sb2099-archive")
    tasks = [ingest_task, recount_task, archive_task]
    log.info("sb2099 startup complete; bg tasks=%s", [t.get_name() for t in tasks])
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except BaseException:
                pass
        log.info("sb2099 shutdown complete")


app = FastAPI(title="sb2099", lifespan=lifespan)
app.state.limiter = limiter


def _rate_limit_handler(request, exc):  # type: ignore[no-untyped-def]
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=429, content={"detail": f"rate limit exceeded: {exc.detail}"})


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)
app.include_router(api_router)
app.include_router(api_admin_router)
app.include_router(public_router)

_FRONTEND_DIST = Path(
    os.environ.get("SB2099_FRONTEND_DIST", str(Path(__file__).parent / "frontend" / "dist"))
)
mount_spa(app, _FRONTEND_DIST)
