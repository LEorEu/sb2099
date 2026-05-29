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
from ._filters import register_filters

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_USERSCRIPT_PATH = Path(__file__).parent.parent / "userscript" / "sb2099.user.js"

templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
register_filters(templates)

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
    from datetime import datetime, timedelta, timezone
    from ..live_day import current_live_window
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    live_date, _ = current_live_window(now)
    if window == "day":
        sql = text(
            "SELECT d.id, d.content_sample, d.send_cnt, d.unique_sender_cnt AS unique_senders, "
            "d.last_seen, b.id AS barrage_id, b.tags AS barrage_tags "
            "FROM daily_hot d "
            "LEFT JOIN barrage b ON b.content_norm = d.content_norm AND b.status='active' "
            "WHERE d.live_date = :d AND d.is_filtered = 0 "
            "ORDER BY d.send_cnt DESC, d.last_seen DESC LIMIT 10"
        )
        params = {"d": live_date.isoformat()}
    else:
        wk_start = (live_date - timedelta(days=6)).isoformat()
        sql = text(
            "SELECT "
            "  (SELECT d2.id FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "     AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS id, "
            "  d.content_norm, "
            "  (SELECT d2.content_sample FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "     AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS content_sample, "
            "  SUM(d.send_cnt) AS send_cnt, MAX(d.unique_sender_cnt) AS unique_senders, "
            "  MAX(d.last_seen) AS last_seen, b.id AS barrage_id, b.tags AS barrage_tags "
            "FROM daily_hot d "
            "LEFT JOIN barrage b ON b.content_norm = d.content_norm AND b.status='active' "
            "WHERE d.live_date >= :wk AND d.is_filtered = 0 "
            "GROUP BY d.content_norm ORDER BY send_cnt DESC, last_seen DESC LIMIT 50"
        )
        params = {"wk": wk_start}
    with _db.SessionLocal() as s:
        rows = s.execute(sql, params).mappings().all()
    items = [
        {
            "id": r["id"],
            "content_sample": r["content_sample"],
            "send_cnt": int(r["send_cnt"] or 0),
            "unique_senders": int(r["unique_senders"] or 0),
            "last_seen": r["last_seen"],
            "barrage_id": r["barrage_id"],
            "barrage_tags": r["barrage_tags"],
        }
        for r in rows
    ]
    return templates.TemplateResponse(
        request=request,
        name="live.html",
        context={"window": window, "items": items, "tags": _enabled_tags()},
    )


@router.get("/userscript")
async def userscript() -> FileResponse:
    return FileResponse(
        _USERSCRIPT_PATH,
        media_type="application/javascript",
        filename="sb2099.user.js",
    )
