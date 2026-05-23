"""7×24 ingest task：消费 client.stream_chat_events()，转交 aggregator 落库。"""
from __future__ import annotations

import asyncio
import logging

from .aggregator import persist_chat_event
from .client import stream_chat_events

log = logging.getLogger(__name__)

__all__ = ["run", "start_background"]


async def run() -> None:
    """无限循环；client 已自带 5s 重连。"""
    async for evt in stream_chat_events():
        try:
            await persist_chat_event(evt)
        except Exception:
            log.exception("persist_chat_event failed; evt=%r", evt)


def start_background() -> asyncio.Task:
    return asyncio.create_task(run(), name="sb2099-ingest")
