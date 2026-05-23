"""FastAPI 实例 + lifespan：startup 拉起 ingest worker，shutdown 取消。"""
from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI

from ..ingest.worker import start_background
from .routes_public import router as public_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sb2099")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ingest_task = start_background()
    log.info("sb2099 startup complete; ingest task=%s", ingest_task.get_name())
    try:
        yield
    finally:
        ingest_task.cancel()
        try:
            await ingest_task
        except BaseException:
            pass
        log.info("sb2099 shutdown complete")


app = FastAPI(title="sb2099", lifespan=lifespan)
app.include_router(public_router)
