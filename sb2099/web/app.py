"""FastAPI 实例 + lifespan：startup 拉起 ingest worker + cron，shutdown 取消。"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..cron import archive_loop, recount_loop
from ..ingest.worker import start_background
from .routes_api import router as api_router
from .routes_public import router as public_router

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
app.include_router(api_router)
app.include_router(public_router)

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
