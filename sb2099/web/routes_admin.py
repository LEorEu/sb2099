"""/admin/* 后台路由占位。Cookie-Token 鉴权按 §2.5 实现。"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/admin")
