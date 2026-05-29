"""7×24 ingest task：消费 danmu_tcp.stream_chat_events()，落库 raw + user。"""
from __future__ import annotations

import asyncio
import logging

from .aggregator import persist_chat_event, persist_user_from_chat
from .danmu_tcp import stream_chat_events

log = logging.getLogger(__name__)

__all__ = ["run", "start_background"]


async def run() -> None:
    """无限循环；danmu_tcp 已自带 5s 重连。"""
    async for evt in stream_chat_events():
        try:
            await persist_chat_event(evt)
            await persist_user_from_chat(evt)
        except Exception:
            log.exception("persist failed; evt=%r", evt)


def start_background() -> asyncio.Task:
    return asyncio.create_task(run(), name="sb2099-ingest")
