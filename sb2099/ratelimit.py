"""slowapi 限流 + IP 哈希工具。占位实现，后续按 §9 路由接入。"""
from __future__ import annotations

import hashlib

from .config import get_settings

__all__ = ["ip_hash"]


def ip_hash(ip: str) -> str:
    """落库前匿名化：sha256(ip + salt)[:16]。"""
    salt = get_settings().SB2099_IP_SALT
    return hashlib.sha256(f"{ip}{salt}".encode()).hexdigest()[:16]
