"""SPA 静态托管：挂载 /assets + 未知前端路由回退到 index.html。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# 这些前缀交给真正的路由/挂载处理，不走 SPA 回退
SPA_EXCLUDE = ("api/", "assets/", "userscript")


def mount_spa(app: FastAPI, dist_dir: Path) -> None:
    """把已构建的 Vue 产物挂到 app 上：/assets 静态 + 通配回退 index.html。

    回退路由必须在所有真实路由之后注册（调用方保证）。
    """
    if (dist_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str, request: Request):  # noqa: ARG001
        if full_path.startswith(SPA_EXCLUDE):
            return JSONResponse(status_code=404, content={"detail": "not found"})
        # dist 根目录下的真实静态文件（logo.jpg / favicon / robots.txt 等）直接返回，
        # 不能被 SPA 回退吃掉。带路径穿越防护：解析后必须仍在 dist 内。
        if full_path and full_path != "index.html":
            try:
                candidate = (dist_dir / full_path).resolve()
                if candidate.is_file() and candidate.is_relative_to(dist_dir.resolve()):
                    return FileResponse(candidate)
            except (OSError, ValueError):
                pass
        index = dist_dir / "index.html"
        if index.is_file():
            return FileResponse(index, media_type="text/html")
        return JSONResponse(status_code=503, content={"detail": "frontend not built"})
