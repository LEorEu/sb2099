"""websockets 客户端：订阅上游 douyu_live VPS /ws/live。

upstream URL 走 `Settings.DOUYU_LIVE_WS_URL`（默认 ws://139.196.96.110:8080/ws/live）。
filter 只放行 `kind=="chat"` 的事件，其它（gift/superchat/subscription/room_info/vip_info）丢弃。
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import websockets

from ..config import get_settings

log = logging.getLogger(__name__)

__all__ = ["stream_chat_events"]


async def stream_chat_events() -> AsyncIterator[dict]:
    """断线 5s 重连的无限 async generator，只 yield kind=='chat' 事件。"""
    url = get_settings().DOUYU_LIVE_WS_URL
    while True:
        try:
            log.info("connecting to %s", url)
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                log.info("connected, waiting for events")
                async for raw in ws:
                    try:
                        evt = json.loads(raw)
                    except json.JSONDecodeError:
                        log.warning("non-json frame: %r", raw[:80])
                        continue
                    if evt.get("kind") == "chat":
                        yield evt
        except (websockets.WebSocketException, OSError) as e:
            log.warning("ws disconnected: %s; retrying in 5s", e)
            await asyncio.sleep(5)
