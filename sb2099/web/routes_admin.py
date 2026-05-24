"""/admin/* 后台路由 — 切片 A。

鉴权走 cookie（见 admin_auth.py）；登录端点会发 HttpOnly SameSite=Strict cookie。
非登录页面在 GET 请求未鉴权时重定向到 /admin/login，POST 请求未鉴权直接 401。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Path as PathParam, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, desc, func, select, text, update

from .. import db as _db
from ..models import Barrage, BarrageReport, LiveHot, RawDanmaku, Setting, Tag
from ..settings import settings_cache
from .admin_auth import COOKIE_MAX_AGE, COOKIE_NAME, require_admin, verify_token

_TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

router = APIRouter(prefix="/admin")


def _is_logged_in(token: str | None) -> bool:
    return bool(token and verify_token(token))


def _redirect_or_401(request: Request, sb2099_admin: str | None) -> None:
    """GET 页面未登录跳 /admin/login；POST 未登录 401。"""
    if _is_logged_in(sb2099_admin):
        return
    if request.method == "GET":
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin/login"},
        )
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin login required")


# ---- login / logout -------------------------------------------------------


@router.get("/login", response_class=HTMLResponse)
def login_form(
    request: Request,
    next: str = "/admin/settings",
    err: str | None = None,
    sb2099_admin: str | None = Cookie(default=None),
) -> HTMLResponse:
    if _is_logged_in(sb2099_admin):
        return RedirectResponse(url=next, status_code=303)  # type: ignore[return-value]
    return templates.TemplateResponse(
        request=request,
        name="admin/login.html",
        context={"next": next, "err": err},
    )


@router.post("/login")
def login_submit(
    token: str = Form(...),
    next: str = Form("/admin/settings"),
):
    if not verify_token(token):
        return RedirectResponse(url=f"/admin/login?err=1&next={next}", status_code=303)
    resp = RedirectResponse(url=next, status_code=303)
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="strict",
    )
    return resp


@router.post("/logout")
def logout():
    resp = RedirectResponse(url="/admin/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


# ---- settings -------------------------------------------------------------


_SETTING_KEYS = [
    "live_hot_min_unique_senders_24h",
    "live_noise_filters",
    "submission_review_rules",
    "barrage_min_length",
    "barrage_max_length",
    "ratelimit_submit_per_hour_per_ip",
    "ratelimit_report_per_hour_per_ip",
    "ratelimit_copy_per_hour_per_ip",
    "ratelimit_promote_per_hour_per_ip",
    "raw_retention_days",
]


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    sb2099_admin: str | None = Cookie(default=None),
) -> HTMLResponse:
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        rows = s.execute(select(Setting.key, Setting.value, Setting.updated_at)).all()
    items = {r.key: (r.value, r.updated_at) for r in rows}
    return templates.TemplateResponse(
        request=request,
        name="admin/settings.html",
        context={"keys": _SETTING_KEYS, "items": items},
    )


@router.post("/settings")
async def settings_update(
    request: Request,
    sb2099_admin: str | None = Cookie(default=None),
):
    _redirect_or_401(request, sb2099_admin)
    form = await request.form()
    now = datetime.utcnow()
    errors: list[str] = []
    with _db.SessionLocal() as s:
        for key in _SETTING_KEYS:
            raw = form.get(key)
            if raw is None:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as e:
                errors.append(f"{key}: invalid JSON ({e})")
                continue
            s.execute(
                update(Setting)
                .where(Setting.key == key)
                .values(value=json.dumps(parsed, ensure_ascii=False), updated_at=now)
            )
        s.commit()
    settings_cache.invalidate()
    if errors:
        return RedirectResponse(
            url=f"/admin/settings?err={','.join(errors)[:200]}", status_code=303
        )
    return RedirectResponse(url="/admin/settings?ok=1", status_code=303)


# ---- tags -----------------------------------------------------------------


_TAG_VALUE_RE = re.compile(r"^[0-9A-Za-z]{1,8}$")


@router.get("/tags", response_class=HTMLResponse)
def tags_page(
    request: Request,
    sb2099_admin: str | None = Cookie(default=None),
) -> HTMLResponse:
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(Tag.value, Tag.label, Tag.icon_url, Tag.sort, Tag.enabled).order_by(Tag.sort)
        ).all()
    return templates.TemplateResponse(
        request=request,
        name="admin/tags.html",
        context={"tags": rows},
    )


@router.post("/tags")
async def tags_create(
    request: Request,
    value: str = Form(...),
    label: str = Form(...),
    icon_url: str = Form(""),
    sort: int = Form(0),
    sb2099_admin: str | None = Cookie(default=None),
):
    _redirect_or_401(request, sb2099_admin)
    if not _TAG_VALUE_RE.match(value):
        raise HTTPException(status_code=400, detail="tag value must be 1-8 alphanumeric chars")
    with _db.SessionLocal() as s:
        if s.get(Tag, value):
            raise HTTPException(status_code=409, detail="tag already exists")
        s.add(Tag(value=value, label=label, icon_url=icon_url or None, sort=sort, enabled=True))
        s.commit()
    return RedirectResponse(url="/admin/tags", status_code=303)


@router.post("/tags/{value}/update")
async def tags_update_one(
    request: Request,
    value: str = PathParam(...),
    label: str = Form(...),
    icon_url: str = Form(""),
    sort: int = Form(0),
    enabled: str = Form(""),
    sb2099_admin: str | None = Cookie(default=None),
):
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        row = s.get(Tag, value)
        if not row:
            raise HTTPException(status_code=404, detail="tag not found")
        row.label = label
        row.icon_url = icon_url or None
        row.sort = sort
        row.enabled = enabled == "1"
        s.commit()
    return RedirectResponse(url="/admin/tags", status_code=303)


@router.post("/tags/{value}/delete")
def tags_delete(
    request: Request,
    value: str = PathParam(...),
    sb2099_admin: str | None = Cookie(default=None),
):
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        row = s.get(Tag, value)
        if not row:
            raise HTTPException(status_code=404, detail="tag not found")
        s.delete(row)
        s.commit()
    return RedirectResponse(url="/admin/tags", status_code=303)


# ---- barrage pending / reports / trash -----------------------------------


@router.get("/barrage/pending", response_class=HTMLResponse)
def pending_page(
    request: Request,
    sb2099_admin: str | None = Cookie(default=None),
) -> HTMLResponse:
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(Barrage)
            .where(Barrage.status == "pending")
            .order_by(desc(Barrage.submit_time))
            .limit(200)
        ).scalars().all()
    return templates.TemplateResponse(
        request=request, name="admin/pending.html", context={"items": rows}
    )


@router.post("/barrage/{barrage_id:int}/approve")
def approve(
    request: Request,
    barrage_id: int,
    tags: str = Form(""),
    sb2099_admin: str | None = Cookie(default=None),
):
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        row = s.get(Barrage, barrage_id)
        if not row:
            raise HTTPException(status_code=404, detail="barrage not found")
        if tags:
            row.tags = tags
        row.status = "active"
        s.commit()
    return RedirectResponse(url="/admin/barrage/pending", status_code=303)


@router.post("/barrage/{barrage_id:int}/reject")
def reject(
    request: Request,
    barrage_id: int,
    sb2099_admin: str | None = Cookie(default=None),
):
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        row = s.get(Barrage, barrage_id)
        if not row:
            raise HTTPException(status_code=404, detail="barrage not found")
        row.status = "deleted"
        s.commit()
    return RedirectResponse(url="/admin/barrage/pending", status_code=303)


@router.get("/barrage/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    sb2099_admin: str | None = Cookie(default=None),
) -> HTMLResponse:
    _redirect_or_401(request, sb2099_admin)
    sql = text(
        """
        SELECT b.id, b.content, b.tags, b.cnt, b.report_cnt, b.status,
               b.submit_time, MAX(r.ts) AS last_report
        FROM barrage b
        LEFT JOIN barrage_report r ON r.barrage_id = b.id
        WHERE b.report_cnt > 0
        GROUP BY b.id
        ORDER BY b.report_cnt DESC, last_report DESC
        LIMIT 200
        """
    )
    with _db.SessionLocal() as s:
        rows = s.execute(sql).mappings().all()
    return templates.TemplateResponse(
        request=request, name="admin/reports.html", context={"items": rows}
    )


@router.get("/barrage/_trash", response_class=HTMLResponse)
def trash_page(
    request: Request,
    sb2099_admin: str | None = Cookie(default=None),
) -> HTMLResponse:
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(Barrage)
            .where(Barrage.status == "deleted")
            .order_by(desc(Barrage.submit_time))
            .limit(200)
        ).scalars().all()
    return templates.TemplateResponse(
        request=request, name="admin/trash.html", context={"items": rows}
    )


@router.post("/barrage/{barrage_id:int}/restore")
def trash_restore(
    request: Request,
    barrage_id: int,
    sb2099_admin: str | None = Cookie(default=None),
):
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        row = s.get(Barrage, barrage_id)
        if not row:
            raise HTTPException(status_code=404, detail="barrage not found")
        row.status = "active"
        s.commit()
    return RedirectResponse(url="/admin/barrage/_trash", status_code=303)


@router.post("/barrage/{barrage_id:int}/purge")
def trash_purge(
    request: Request,
    barrage_id: int,
    sb2099_admin: str | None = Cookie(default=None),
):
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        # 顺手清掉相关 reports
        s.execute(delete(BarrageReport).where(BarrageReport.barrage_id == barrage_id))
        s.execute(delete(Barrage).where(Barrage.id == barrage_id))
        s.commit()
    return RedirectResponse(url="/admin/barrage/_trash", status_code=303)


# ---- live_hot list / detail / rescan -------------------------------------


@router.get("/live_hot", response_class=HTMLResponse)
def live_hot_page(
    request: Request,
    filtered: bool = Query(False),
    sb2099_admin: str | None = Cookie(default=None),
) -> HTMLResponse:
    _redirect_or_401(request, sb2099_admin)
    where = "is_filtered=1" if filtered else "1=1"
    sql = text(
        f"SELECT id, content_sample, send_cnt_24h, send_cnt_total, "
        "unique_sender_cnt_24h, last_seen, is_filtered "
        f"FROM live_hot WHERE {where} "
        "ORDER BY send_cnt_total DESC LIMIT 200"
    )
    with _db.SessionLocal() as s:
        rows = s.execute(sql).mappings().all()
    return templates.TemplateResponse(
        request=request,
        name="admin/live_hot.html",
        context={"items": rows, "filtered": filtered},
    )


@router.get("/live_hot/{live_hot_id:int}", response_class=HTMLResponse)
def live_hot_detail(
    request: Request,
    live_hot_id: int,
    sb2099_admin: str | None = Cookie(default=None),
) -> HTMLResponse:
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        hot = s.get(LiveHot, live_hot_id)
        if not hot:
            raise HTTPException(status_code=404, detail="live_hot not found")
        sql = text(
            "SELECT uid, nickname, ts, content_raw FROM raw_danmaku "
            "WHERE content_norm = :cn ORDER BY ts DESC LIMIT 500"
        )
        raws = s.execute(sql, {"cn": hot.content_norm}).mappings().all()
        # 按 uid 聚合识别刷子
        uid_cnt: dict[str, int] = {}
        for r in raws:
            if r["uid"]:
                uid_cnt[r["uid"]] = uid_cnt.get(r["uid"], 0) + 1
        top_uids = sorted(uid_cnt.items(), key=lambda x: -x[1])[:30]
    return templates.TemplateResponse(
        request=request,
        name="admin/live_hot_detail.html",
        context={"hot": hot, "raws": raws, "top_uids": top_uids},
    )


@router.post("/live_hot/rescan")
def live_hot_rescan(
    request: Request,
    sb2099_admin: str | None = Cookie(default=None),
):
    """改完 live_noise_filters 后调一次：扫所有 live_hot，重算 is_filtered。

    复用 tools/backfill_live_hot 的核心思路：对每个 content_norm，看其下任一
    raw_danmaku.content_raw 是否命中当前规则的子串。
    """
    _redirect_or_401(request, sb2099_admin)
    settings_cache.invalidate()
    filters = settings_cache.get("live_noise_filters", []) or []
    n_filtered = 0
    n_unfiltered = 0
    with _db.SessionLocal() as s:
        rows = s.execute(select(LiveHot.id, LiveHot.content_norm)).all()
        for hot_id, cn in rows:
            raws = (
                s.execute(
                    select(RawDanmaku.content_raw).where(RawDanmaku.content_norm == cn)
                )
                .scalars()
                .all()
            )
            hit = any(any(kw and kw in r for kw in filters) for r in raws) if filters else False
            s.execute(update(LiveHot).where(LiveHot.id == hot_id).values(is_filtered=hit))
            if hit:
                n_filtered += 1
            else:
                n_unfiltered += 1
        s.commit()
    return RedirectResponse(
        url=f"/admin/live_hot?rescan_ok={n_filtered}_filtered_{n_unfiltered}_clear", status_code=303
    )


# ---- stats ----------------------------------------------------------------


@router.get("/stats", response_class=HTMLResponse)
def stats_page(
    request: Request,
    sb2099_admin: str | None = Cookie(default=None),
) -> HTMLResponse:
    _redirect_or_401(request, sb2099_admin)
    now = datetime.utcnow()
    h24 = now - timedelta(hours=24)

    with _db.SessionLocal() as s:
        raw_24h = s.execute(
            select(func.count(RawDanmaku.id)).where(RawDanmaku.ts >= h24)
        ).scalar_one()
        submit_24h = s.execute(
            select(func.count(Barrage.id)).where(Barrage.submit_time >= h24)
        ).scalar_one()
        copy_24h = s.execute(select(func.sum(Barrage.cnt))).scalar() or 0
        live_hot_total = s.execute(select(func.count(LiveHot.id))).scalar_one()
        pending_total = s.execute(
            select(func.count(Barrage.id)).where(Barrage.status == "pending")
        ).scalar_one()
        deleted_total = s.execute(
            select(func.count(Barrage.id)).where(Barrage.status == "deleted")
        ).scalar_one()
        report_24h = s.execute(
            select(func.count(BarrageReport.id)).where(BarrageReport.ts >= h24)
        ).scalar_one()

        # TOP 投稿者 IP（24h）
        top_ip_rows = s.execute(
            text(
                """
                SELECT submitter_ip_hash, COUNT(*) AS n
                FROM barrage
                WHERE submit_time >= :h24 AND submitter_ip_hash IS NOT NULL
                GROUP BY submitter_ip_hash
                ORDER BY n DESC
                LIMIT 20
                """
            ),
            {"h24": h24},
        ).all()

    return templates.TemplateResponse(
        request=request,
        name="admin/stats.html",
        context={
            "raw_24h": raw_24h,
            "submit_24h": submit_24h,
            "copy_total": copy_24h,
            "live_hot_total": live_hot_total,
            "pending_total": pending_total,
            "deleted_total": deleted_total,
            "report_24h": report_24h,
            "top_ip": top_ip_rows,
        },
    )
