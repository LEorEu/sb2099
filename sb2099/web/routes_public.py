"""公开页路由占位：首页 / 投稿库 / 热门弹幕。

第一版只实现 GET /，证明 FastAPI 实例 + Jinja2 模板加载链路通畅。
后续按 §8 表补全 /barrage、/live、/userscript。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

_TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="home.html", context={})
