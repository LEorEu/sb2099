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
from ._filters import register_filters
from .admin_auth import COOKIE_MAX_AGE, COOKIE_NAME, require_admin, verify_token

_TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))
register_filters(templates)

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


# 后台「运行时参数设置」的展示元数据。
# kind:
#   "int"   → 单个整数,textarea rows=1
#   "lines" → 每行一条字符串,后端 split('\n')、strip、去空行后存为 JSON 数组
_SETTING_META: list[dict[str, object]] = [
    {
        "key": "live_hot_min_unique_senders_24h",
        "label": "直播热门门槛(24h 不同发送者人数)",
        "desc": "24h 内有多少不同账号刷过同一条弹幕,才允许进入热门榜",
        "kind": "int",
        "default": 3,
        "hint": "整数,建议 3 – 10",
    },
    {
        "key": "live_hot_min_length",
        "label": "直播热门最短字数",
        "desc": "归一化后短于此长度,或全是数字/标点/emoji 的弹幕直接进入「过滤」分组",
        "kind": "int",
        "default": 2,
        "hint": "整数,建议 2 – 4",
    },
    {
        "key": "live_hot_max_length",
        "label": "直播热门最长字数",
        "desc": "归一化后长于此字数直接进入「过滤」分组(防止超长复制刷屏)。设为 0 表示不限",
        "kind": "int",
        "default": 80,
        "hint": "整数,建议 60 – 120;0 = 不限",
    },
    {
        "key": "live_noise_filters",
        "label": "直播降噪关键词",
        "desc": "弹幕全文完全等于其中任一条时,不进入热门榜",
        "kind": "lines",
        "default": [],
        "hint": "每行一条;采用「整句精确匹配」,不会被子串误伤",
    },
    {
        "key": "submission_review_rules",
        "label": "投稿待审关键词",
        "desc": "投稿正文包含任一关键词时,先进入 pending 等管理员审核",
        "kind": "lines",
        "default": [],
        "hint": "每行一条;子串包含即命中(用于违禁词等强风险词)",
    },
    {
        "key": "barrage_min_length",
        "label": "投稿最少字数",
        "desc": "正文短于此字数会被拒收",
        "kind": "int",
        "default": 4,
        "hint": "整数,建议 1 – 50",
    },
    {
        "key": "barrage_max_length",
        "label": "投稿最多字数",
        "desc": "正文长于此字数会被拒收",
        "kind": "int",
        "default": 255,
        "hint": "整数,建议 ≤ 500",
    },
    {
        "key": "ratelimit_submit_per_hour_per_ip",
        "label": "每 IP 每小时投稿次数上限",
        "desc": "超过上限返回 429",
        "kind": "int",
        "default": 5,
        "hint": "整数",
    },
    {
        "key": "ratelimit_report_per_hour_per_ip",
        "label": "每 IP 每小时「不合适」反馈次数",
        "desc": "针对投稿库条目的负反馈频率上限",
        "kind": "int",
        "default": 60,
        "hint": "整数",
    },
    {
        "key": "ratelimit_copy_per_hour_per_ip",
        "label": "每 IP 每小时复制次数",
        "desc": "复制即累加 cnt;到达上限后该 IP 当小时不再计入",
        "kind": "int",
        "default": 200,
        "hint": "整数",
    },
    {
        "key": "ratelimit_promote_per_hour_per_ip",
        "label": "每 IP 每小时「提升入库」次数",
        "desc": "从直播热门往投稿库补 tag 提升的频率上限",
        "kind": "int",
        "default": 5,
        "hint": "整数",
    },
    {
        "key": "raw_retention_days",
        "label": "原始弹幕保留天数",
        "desc": "raw_danmaku 表保留窗口;archive_cron 每日 04:00 删早于该窗口的行",
        "kind": "int",
        "default": 30,
        "hint": "整数",
    },
]

_SETTING_KEYS = [m["key"] for m in _SETTING_META]
_SETTING_KIND = {m["key"]: m["kind"] for m in _SETTING_META}


def _render_setting_value(raw_db_value: str | None, kind: str) -> str:
    """把数据库里 JSON 序列化后的值反序列化成 textarea 显示文本。"""
    if raw_db_value is None or raw_db_value == "":
        return ""
    try:
        parsed = json.loads(raw_db_value)
    except (TypeError, json.JSONDecodeError):
        return raw_db_value
    if kind == "lines":
        if isinstance(parsed, list):
            return "\n".join(str(x) for x in parsed)
        return str(parsed)
    return str(parsed)


def _parse_setting_input(raw_form_value: str, kind: str) -> object:
    """把表单原始字符串按 kind 解析成要落库的 Python 对象;失败抛 ValueError。"""
    if kind == "int":
        text_value = raw_form_value.strip()
        if text_value == "":
            raise ValueError("不能为空")
        try:
            return int(text_value)
        except ValueError as e:
            raise ValueError(f"请输入整数(收到: {text_value!r})") from e
    if kind == "lines":
        return [line.strip() for line in raw_form_value.splitlines() if line.strip()]
    raise ValueError(f"未知 kind: {kind}")


@router.get("/settings", response_class=HTMLResponse)
def settings_page(
    request: Request,
    sb2099_admin: str | None = Cookie(default=None),
) -> HTMLResponse:
    _redirect_or_401(request, sb2099_admin)
    with _db.SessionLocal() as s:
        rows = s.execute(select(Setting.key, Setting.value)).all()
    db_values = {r.key: r.value for r in rows}
    items = []
    for meta in _SETTING_META:
        items.append(
            {
                **meta,
                "value_text": _render_setting_value(db_values.get(meta["key"]), meta["kind"]),
            }
        )
    return templates.TemplateResponse(
        request=request,
        name="admin/settings.html",
        context={"items": items},
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
            kind = _SETTING_KIND[key]
            try:
                parsed = _parse_setting_input(str(raw), kind)
            except ValueError as e:
                errors.append(f"{key}: {e}")
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


@router.post("/live_hot/recompute")
def live_hot_recompute(
    request: Request,
    sb2099_admin: str | None = Cookie(default=None),
):
    """重 normalize 所有 raw_danmaku → 重建 live_hot 聚合。
    用于规则变更(如重复折叠)后,把历史 N 个变体合并到一条 base。
    """
    from ..ingest.aggregator import should_filter
    from ..normalize import normalize

    _redirect_or_401(request, sb2099_admin)
    settings_cache.invalidate()
    with _db.SessionLocal() as s:
        # 1) 重 normalize 所有 raw_danmaku.content_norm
        rows = s.execute(
            select(RawDanmaku.id, RawDanmaku.content_raw, RawDanmaku.content_norm)
        ).all()
        n_raw_updated = 0
        for rid, raw, old_norm in rows:
            new_norm = normalize(raw or "")
            if new_norm != old_norm:
                s.execute(
                    update(RawDanmaku).where(RawDanmaku.id == rid).values(content_norm=new_norm)
                )
                n_raw_updated += 1
        # 2) 清空 live_hot,从 raw 重新聚合
        s.execute(text("DELETE FROM live_hot"))
        s.execute(
            text(
                "INSERT INTO live_hot(content_norm, content_sample, first_seen, last_seen, "
                "send_cnt_total, send_cnt_24h, send_cnt_7d, "
                "unique_sender_cnt_24h, unique_sender_cnt_7d, is_filtered) "
                "SELECT content_norm, "
                "  (SELECT content_raw FROM raw_danmaku r2 WHERE r2.content_norm = r.content_norm "
                "    ORDER BY LENGTH(r2.content_raw) ASC, ts DESC LIMIT 1), "
                "  MIN(ts), MAX(ts), COUNT(*), 0, 0, 0, 0, 0 "
                "FROM raw_danmaku r WHERE content_norm <> '' GROUP BY content_norm"
            )
        )
        # 3) 重算 is_filtered
        live_rows = s.execute(select(LiveHot.id, LiveHot.content_norm)).all()
        n_filtered = 0
        for hot_id, cn in live_rows:
            if should_filter(cn):
                s.execute(update(LiveHot).where(LiveHot.id == hot_id).values(is_filtered=True))
                n_filtered += 1
        s.commit()
    # 4) 触发一次 recount 把 24h/7d/unique 重算
    from ..cron import _recount_sync
    _recount_sync()
    return RedirectResponse(
        url=f"/admin/live_hot?recompute_ok={n_raw_updated}_raw_renorm_{len(live_rows)}_aggregated_{n_filtered}_filtered",
        status_code=303,
    )


@router.post("/live_hot/rescan")
def live_hot_rescan(
    request: Request,
    sb2099_admin: str | None = Cookie(default=None),
):
    """改完 live_noise_filters / live_hot_min_length 后调一次:
    扫所有 live_hot,按当前规则(整句精确匹配 + 长度/字符过滤)重算 is_filtered。
    """
    from ..ingest.aggregator import should_filter

    _redirect_or_401(request, sb2099_admin)
    settings_cache.invalidate()
    n_filtered = 0
    n_unfiltered = 0
    with _db.SessionLocal() as s:
        rows = s.execute(select(LiveHot.id, LiveHot.content_norm)).all()
        for hot_id, cn in rows:
            hit = should_filter(cn)
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
