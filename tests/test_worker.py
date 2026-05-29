"""ingest worker producer/consumer 解耦语义测试。"""
from __future__ import annotations

import asyncio

import pytest

from sb2099.ingest import worker


@pytest.mark.asyncio
async def test_producer_not_blocked_by_slow_consumer(monkeypatch):
    """关键回归：consumer 写库慢时 producer 不能被反压住。

    旧版 async for + 双 await 的串行结构在突发流量下会反压 reader 导致
    斗鱼侧丢消息。新版用 asyncio.Queue 解耦后 producer 立即返回。
    """
    events = [{"uid": str(i), "content": f"m{i}"} for i in range(50)]
    consumed: list[dict] = []
    consume_started = asyncio.Event()
    release_consumer = asyncio.Event()

    async def fake_stream():
        for e in events:
            yield e

    async def slow_persist_chat(e):
        consume_started.set()
        await release_consumer.wait()
        consumed.append(e)

    async def fake_persist_user(e):
        return

    monkeypatch.setattr(worker, "stream_chat_events", fake_stream)
    monkeypatch.setattr(worker, "persist_chat_event", slow_persist_chat)
    monkeypatch.setattr(worker, "persist_user_from_chat", fake_persist_user)

    queue: asyncio.Queue[dict] = asyncio.Queue()
    prod_task = asyncio.create_task(worker._produce(queue))
    cons_task = asyncio.create_task(worker._consume(queue))

    # producer 必须能跑完所有 50 条而不被 consumer 阻塞
    await asyncio.wait_for(prod_task, timeout=1.0)
    await consume_started.wait()
    assert queue.qsize() >= 40, f"queue should be deep, got {queue.qsize()}"
    assert len(consumed) <= 1, "consumer was paused but producer kept producing"

    release_consumer.set()
    await asyncio.wait_for(queue.join(), timeout=2.0)
    cons_task.cancel()
    assert len(consumed) == 50


@pytest.mark.asyncio
async def test_consumer_survives_persist_exception(monkeypatch):
    """单条 persist 抛异常不能让 consumer 死掉，下一条继续。"""
    events = [{"uid": "1", "content": "boom"}, {"uid": "2", "content": "ok"}]
    consumed: list[str] = []

    async def fake_stream():
        for e in events:
            yield e

    async def explosive_persist_chat(e):
        if e["content"] == "boom":
            raise RuntimeError("simulated DB error")
        consumed.append(e["content"])

    async def fake_persist_user(e):
        return

    monkeypatch.setattr(worker, "stream_chat_events", fake_stream)
    monkeypatch.setattr(worker, "persist_chat_event", explosive_persist_chat)
    monkeypatch.setattr(worker, "persist_user_from_chat", fake_persist_user)

    queue: asyncio.Queue[dict] = asyncio.Queue()
    prod_task = asyncio.create_task(worker._produce(queue))
    cons_task = asyncio.create_task(worker._consume(queue))

    await asyncio.wait_for(prod_task, timeout=1.0)
    await asyncio.wait_for(queue.join(), timeout=2.0)
    cons_task.cancel()
    assert consumed == ["ok"]
