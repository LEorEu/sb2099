"""管理员鉴权：登录走 SB2099_ADMIN_TOKEN，发 30 天 HttpOnly cookie。"""
from __future__ import annotations

import hmac

from fastapi import Cookie, HTTPException, status

from ..config import get_settings

__all__ = ["COOKIE_NAME", "COOKIE_MAX_AGE", "require_admin", "verify_token"]

COOKIE_NAME = "sb2099_admin"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 天


def verify_token(token: str) -> bool:
    """常量时间比对 SB2099_ADMIN_TOKEN。"""
    expected = get_settings().SB2099_ADMIN_TOKEN
    if not expected or not token:
        return False
    return hmac.compare_digest(token, expected)


def require_admin(sb2099_admin: str | None = Cookie(default=None)) -> str:
    """FastAPI Depends：未登录 → 401。"""
    if not sb2099_admin or not verify_token(sb2099_admin):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin login required")
    return sb2099_admin
