"""公开页 SSR：/、/barrage、/live、/userscript。"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text

from .. import db as _db
from ..models import Tag
from ..search import search_barrage

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_USERSCRIPT_PATH = Path(__file__).parent.parent / "userscript" / "sb2099.user.js"

templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

router = APIRouter()


def _enabled_tags() -> list[dict]:
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(Tag.value, Tag.label, Tag.icon_url, Tag.sort)
            .where(Tag.enabled.is_(True))
            .order_by(Tag.sort)
        ).all()
    return [
        {"value": r.value, "label": r.label, "icon_url": r.icon_url, "sort": r.sort}
        for r in rows
    ]


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="home.html", context={"tags": _enabled_tags()}
    )


@router.get("/barrage", response_class=HTMLResponse)
async def barrage_page(
    request: Request,
    q: str | None = None,
    tag: str | None = Query(None),
    sort: Literal["new", "hot"] = "new",
    page: int = Query(1, ge=1),
) -> HTMLResponse:
    tags = [t for t in tag.split(",") if t] if tag else None
    result = search_barrage(q=q, tags=tags, sort=sort, page=page, size=20)
    return templates.TemplateResponse(
        request=request,
        name="list.html",
        context={
            "tags": _enabled_tags(),
            "q": q or "",
            "selected_tags": set(tags or []),
            "sort": sort,
            "page": page,
            "result": result,
        },
    )


@router.get("/live", response_class=HTMLResponse)
async def live_page(
    request: Request,
    window: Literal["day", "week"] = "day",
) -> HTMLResponse:
    cnt_col, uniq_col, limit = (
        ("send_cnt_24h", "unique_sender_cnt_24h", 10)
        if window == "day"
        else ("send_cnt_7d", "unique_sender_cnt_7d", 50)
    )
    sql = text(
        f"SELECT id, content_sample, {cnt_col} AS send_cnt, {uniq_col} AS unique_senders, "
        "last_seen FROM live_hot WHERE is_filtered=0 "
        f"ORDER BY {cnt_col} DESC, last_seen DESC LIMIT :limit"
    )
    with _db.SessionLocal() as s:
        rows = s.execute(sql, {"limit": limit}).mappings().all()
    items = [
        {
            "id": r["id"],
            "content_sample": r["content_sample"],
            "send_cnt": int(r["send_cnt"] or 0),
            "unique_senders": int(r["unique_senders"] or 0),
            "last_seen": r["last_seen"],
        }
        for r in rows
    ]
    return templates.TemplateResponse(
        request=request,
        name="live.html",
        context={"window": window, "items": items},
    )


@router.get("/userscript")
async def userscript() -> FileResponse:
    return FileResponse(
        _USERSCRIPT_PATH,
        media_type="application/javascript",
        filename="sb2099.user.js",
    )
