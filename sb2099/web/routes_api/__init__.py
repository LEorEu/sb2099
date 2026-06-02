"""/api/* JSON 路由聚合。

原单文件 routes_api.py 按域拆成子模块；对外仍暴露单个 `router`（app.py / conftest 不变）。
切片 R（只读）：tags / live / barrage_read / users / presence
切片 W（写入）：submission / interactions
/admin 由 routes_api_admin.py 负责。
"""
from __future__ import annotations

from fastapi import APIRouter

from . import barrage_read, interactions, live, presence, submission, tags, users

router = APIRouter()
for _m in (tags, live, barrage_read, users, presence, submission, interactions):
    router.include_router(_m.router)

__all__ = ["router"]
