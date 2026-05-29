"""7×24 ingest task：consume danmu_tcp.stream_chat_events()，落库 raw + user。

reader producer / sqlite consumer 用 asyncio.Queue 解耦——避免 await sqlite 写
反压 TCP reader 导致斗鱼侧高峰段丢消息。
"""
from __future__ import annotations

import asyncio
import logging

from .aggregator import persist_chat_event, persist_user_from_chat
from .danmu_tcp import stream_chat_events

log = logging.getLogger(__name__)

__all__ = ["run", "start_background"]

_QUEUE_WARN_STEP = 200  # depth 每涨满一个 step 打一次 WARN，避免刷屏


async def _consume(queue: "asyncio.Queue[dict]") -> None:
    while True:
        evt = await queue.get()
        try:
            await persist_chat_event(evt)
            await persist_user_from_chat(evt)
        except Exception:
            log.exception("persist failed; evt=%r", evt)
        finally:
            queue.task_done()


async def _produce(queue: "asyncio.Queue[dict]") -> None:
    async for evt in stream_chat_events():
        queue.put_nowait(evt)
        depth = queue.qsize()
        if depth and depth % _QUEUE_WARN_STEP == 0:
            log.warning("ingest queue depth=%d, persist falling behind", depth)


async def run() -> None:
    queue: asyncio.Queue[dict] = asyncio.Queue()
    await asyncio.gather(_produce(queue), _consume(queue))


def start_background() -> asyncio.Task:
    return asyncio.create_task(run(), name="sb2099-ingest")
