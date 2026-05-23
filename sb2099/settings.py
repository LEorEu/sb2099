"""运行时配置缓存：从 `setting` 表读 JSON 值，TTL 后失效自动重载。

设计文档 §2.5 / §6 / P1-2 / P1-3 硬约束：阈值、降噪规则、待审规则必须从
`setting` 表读，禁止在业务模块里硬编码常量。本模块是统一访问入口。
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any

from sqlalchemy import select

from . import db as _db
from .models import Setting

__all__ = ["SettingsCache", "settings_cache"]

_TTL_SECONDS = 30.0


class SettingsCache:
    """线程安全 TTL 缓存。同进程内 ingest task / cron / web 共享一个实例。"""

    def __init__(self, ttl: float = _TTL_SECONDS) -> None:
        self._ttl = ttl
        self._lock = threading.Lock()
        self._snapshot: dict[str, Any] = {}
        self._loaded_at: float = 0.0

    def _refresh_locked(self) -> None:
        with _db.SessionLocal() as session:
            rows = session.execute(select(Setting.key, Setting.value)).all()
        snap: dict[str, Any] = {}
        for key, value in rows:
            try:
                snap[key] = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                snap[key] = value
        self._snapshot = snap
        self._loaded_at = time.monotonic()

    def _ensure_fresh(self) -> None:
        if time.monotonic() - self._loaded_at < self._ttl and self._snapshot:
            return
        with self._lock:
            if time.monotonic() - self._loaded_at < self._ttl and self._snapshot:
                return
            self._refresh_locked()

    def get(self, key: str, default: Any = None) -> Any:
        self._ensure_fresh()
        return self._snapshot.get(key, default)

    def invalidate(self) -> None:
        """后台改完 setting 后调用，强制下次访问重载。"""
        with self._lock:
            self._loaded_at = 0.0


settings_cache = SettingsCache()
