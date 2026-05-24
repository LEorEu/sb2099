"""slowapi 限流 + IP 哈希。

设计文档 §9 默认限流（写入路径）：
- `POST /api/copy` 200/h/IP
- `POST /api/barrage/report` 60/h/IP
- `POST /api/barrage` 5/h/IP
- `POST /api/promote` 5/h/IP

阈值从 `setting` 表读，运行时可改（P1-2 / P1-3 硬约束）。
"""
from __future__ import annotations

import hashlib

from fastapi import Request
from slowapi import Limiter

from .config import get_settings
from .settings import settings_cache

__all__ = ["ip_hash", "extract_ip", "key_func", "limiter", "rate_for"]


def ip_hash(ip: str) -> str:
    """落库前匿名化：sha256(ip + salt)[:16]。"""
    salt = get_settings().SB2099_IP_SALT
    return hashlib.sha256(f"{ip}{salt}".encode()).hexdigest()[:16]


def extract_ip(request: Request) -> str:
    """信任 `X-Forwarded-For` 第一个（设计文档 §9 原文）；fallback 到 socket peer。"""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",", 1)[0].strip()
        if first:
            return first
    client = request.client
    return client.host if client else "0.0.0.0"


def key_func(request: Request) -> str:
    """slowapi 用的速率桶 key：基于 ip_hash，跨进程稳定且不泄露明文 IP。"""
    return ip_hash(extract_ip(request))


def rate_for(setting_key: str, default: int) -> str:
    """从 setting 表读阈值，返回 slowapi 限速字符串如 `"5/hour"`。"""
    n = int(settings_cache.get(setting_key, default) or default)
    return f"{max(1, n)}/hour"


limiter = Limiter(key_func=key_func)
