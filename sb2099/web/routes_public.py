"""公开静态资源：仅 /userscript（返回 .user.js 文件）。其余页面交给 SPA。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

_USERSCRIPT_PATH = Path(__file__).parent.parent / "userscript" / "sb2099.user.js"

router = APIRouter()


@router.get("/userscript")
async def userscript() -> FileResponse:
    return FileResponse(
        _USERSCRIPT_PATH,
        media_type="application/javascript",
        filename="sb2099.user.js",
    )
