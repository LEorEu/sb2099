"""直连斗鱼 danmuproxy.douyu.com:8601，订阅本房间 chatmsg。

不依赖任何上游服务（hyacinth_sentry / douyu_live）。协议是斗鱼自有 TCP 协议：
12 字节头 + body + \\x00。body 用 `key@=value/` 编码，值里的特殊字符做了一级转义
(`@S`→`/`、`@A`→`@`)。

stream_chat_events() 是 7×24 无限 async generator，断线 5s 重连。yield 的 dict
含 ic(头像路径) / level / 粉丝牌字段，下游 aggregator 同时写 raw_danmaku 和 user 表。
"""
from __future__ import annotations

import asyncio
import logging
import struct
import time
from collections.abc import AsyncIterator
from typing import Iterator

from ..config import get_settings

log = logging.getLogger(__name__)

__all__ = ["stream_chat_events"]

_HOST = "danmuproxy.douyu.com"
_PORT = 8601
_HEARTBEAT_INTERVAL = 40.0  # 秒；斗鱼侧约 45s 不收心跳就踢
_RECONNECT_DELAY = 5.0
# 斗鱼对繁忙房间按 gid 分片下发 chatmsg，单 -9999 只拿到一部分。
# 2026-05-29 探针验证：6 个 gid 全订 + cid 去重统计 = 0 跨群重复，所以多群无副本。
_GIDS_TO_JOIN: tuple[int, ...] = (-9999, 1, 2, 3, 4, 5)

_HEADER = struct.Struct("<IIHBB")  # total_len, total_len_dup, msg_type, encrypt, reserved
_CLIENT_TO_SERVER = 689


def _encode(body: str) -> bytes:
    payload = body.encode("utf-8") + b"\x00"
    total_len = 4 + 2 + 1 + 1 + len(payload)  # 不含开头 4 字节长度自身
    return _HEADER.pack(total_len, total_len, _CLIENT_TO_SERVER, 0, 0) + payload


def _iter_frames(buf: bytearray) -> Iterator[str]:
    """从缓冲解出完整 frame body，消费 buf。"""
    while True:
        if len(buf) < 12:
            return
        total_len = struct.unpack_from("<I", buf, 0)[0]
        frame_size = total_len + 4
        if len(buf) < frame_size:
            return
        body = bytes(buf[12:frame_size]).rstrip(b"\x00")
        del buf[:frame_size]
        try:
            yield body.decode("utf-8", errors="replace")
        except Exception:
            continue


def _parse_kv(body: str) -> dict[str, str]:
    """解 `key@=value/...` body；值里转义 @S→/、@A→@。"""
    out: dict[str, str] = {}
    for part in body.split("/"):
        if not part or "@=" not in part:
            continue
        k, _, v = part.partition("@=")
        out[k] = v.replace("@S", "/").replace("@A", "@")
    return out


def _to_int(v: str | None) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _chatmsg_to_event(kv: dict[str, str], room_id: int) -> dict | None:
    """chatmsg KV → 标准化事件 dict。txt/uid 缺则丢弃。"""
    uid = kv.get("uid")
    txt = kv.get("txt")
    if not uid or not txt:
        return None
    return {
        "ts": int(time.time() * 1000),
        "kind": "chat",
        "room_id": room_id,
        "uid": uid,
        "nickname": kv.get("nn"),
        "content": txt,
        "color": _to_int(kv.get("col")),
        "ic": kv.get("ic"),       # 协议已解码，例 avatar_v3/202605/xxx
        "level": _to_int(kv.get("level")),
        "bnn": kv.get("bnn"),
        "brid": kv.get("brid"),
        "bl": _to_int(kv.get("bl")),
        "dms": kv.get("dms"),
    }


async def _one_session(room_id: int) -> AsyncIterator[dict]:
    """单次 TCP 连接：登录 → 加群 → 心跳 → 解 frame → yield chat。

    异常向上传播给 stream_chat_events() 处理重连。
    """
    reader, writer = await asyncio.open_connection(_HOST, _PORT)
    log.info(
        "connected to %s:%d, joining room %d gids=%s",
        _HOST, _PORT, room_id, list(_GIDS_TO_JOIN),
    )
    writer.write(_encode(f"type@=loginreq/roomid@={room_id}/"))
    for gid in _GIDS_TO_JOIN:
        writer.write(_encode(f"type@=joingroup/rid@={room_id}/gid@={gid}/"))
    await writer.drain()

    async def _heartbeat() -> None:
        try:
            while True:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                writer.write(_encode("type@=mrkl/"))
                await writer.drain()
        except (ConnectionError, OSError):
            return  # 写失败由主循环 reader.read 端感知

    hb_task = asyncio.create_task(_heartbeat(), name="danmu-tcp-hb")
    buf = bytearray()
    try:
        while True:
            chunk = await reader.read(8192)
            if not chunk:
                log.warning("server closed connection")
                return
            buf.extend(chunk)
            for body in _iter_frames(buf):
                kv = _parse_kv(body)
                if kv.get("type") != "chatmsg":
                    continue
                evt = _chatmsg_to_event(kv, room_id)
                if evt is not None:
                    yield evt
    finally:
        hb_task.cancel()
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def stream_chat_events() -> AsyncIterator[dict]:
    """无限循环：断线 5s 重连，只 yield 来自本房间的 chatmsg 标准化事件。"""
    room_id = get_settings().DOUYU_ROOM_ID
    while True:
        try:
            async for evt in _one_session(room_id):
                yield evt
        except (OSError, asyncio.IncompleteReadError) as e:
            log.warning("danmu_tcp disconnected: %s; retrying in %.0fs", e, _RECONNECT_DELAY)
        except Exception:
            log.exception("danmu_tcp unexpected error; retrying in %.0fs", _RECONNECT_DELAY)
        await asyncio.sleep(_RECONNECT_DELAY)
