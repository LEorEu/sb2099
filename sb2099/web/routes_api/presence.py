"""在线人数心跳 + 油猴脚本版本号。"""
from __future__ import annotations

import threading
import time

from fastapi import APIRouter, Request

from ... import __version__ as sb_version
from ...ratelimit import extract_ip, ip_hash

router = APIRouter(prefix="/api")


@router.get("/userscript/version")
def get_userscript_version() -> dict:
    return {"version": sb_version}


# ---- 在线人数（心跳 presence）-------------------------------------------
# HTTP 是请求-响应、不会主动告诉服务端谁还开着页面，所以靠前端每隔几十秒来一次
# 心跳：服务端在内存里记 ip_hash -> 最近一次心跳时间，滑动窗口内的不同 ip_hash 数
# 即为「在线」。按 ip_hash 去重而非客户端 id：隐私安全、且天然防同人多标签灌水。
# 单进程内存态（本部署 uvicorn 单 worker）；多 worker 部署需换共享存储。
_PRESENCE_WINDOW_SECONDS = 75.0
_presence_lock = threading.Lock()
_presence: dict[str, float] = {}


@router.get("/presence")
def presence(request: Request) -> dict:
    iph = ip_hash(extract_ip(request))
    now = time.time()
    cutoff = now - _PRESENCE_WINDOW_SECONDS
    with _presence_lock:
        _presence[iph] = now
        for k in [k for k, v in _presence.items() if v < cutoff]:
            del _presence[k]
        n = len(_presence)
    return {"online": n}
