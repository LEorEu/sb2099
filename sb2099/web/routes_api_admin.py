"""/api/admin/* —— 后台 JSON 接口（供 Vue admin SPA 消费）。

鉴权沿用 admin cookie（HttpOnly，见 admin_auth.py）：
  - POST /login 校验 token 后下发同款 cookie；
  - 其余端点用 require_admin Depends，未登录直接 401（不重定向，交给前端守卫跳登录）。
行为与旧 Jinja /admin 路由一一对应，仅把 HTML 渲染换成 JSON。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import bindparam, delete, desc, func, select, text, update

from .. import db as _db
from ..models import (
    Barrage,
    BarrageReport,
    BarrageTagVote,
    DailyHot,
    RawDanmaku,
    Setting,
    Tag,
    User,
)
from ..settings import settings_cache
from ..tag_voting import settle_all_for_tag, vote_threshold
from ..users import avatar_url
from .admin_auth import (
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    require_admin,
    verify_token,
)
from .settings_meta import (
    SETTING_KEYS,
    SETTING_KIND,
    SETTING_META,
    parse_setting_input,
    typed_setting_value,
)

router = APIRouter(prefix="/api/admin")


def _iso(v) -> str | None:
    """UTC naive datetime / SQLite TEXT → ISO 字符串（前端再转 CST 展示）。"""
    if v is None or v == "":
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


# ---- auth -----------------------------------------------------------------


class LoginIn(BaseModel):
    token: str


@router.post("/login")
def login(body: LoginIn, response: Response) -> dict:
    if not verify_token(body.token):
        raise HTTPException(status_code=401, detail="token 不正确")
    response.set_cookie(
        key=COOKIE_NAME,
        value=body.token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(_: str = Depends(require_admin)) -> dict:
    """路由守卫用：登录态 200，否则 401。"""
    return {"authenticated": True}


# ---- settings -------------------------------------------------------------


@router.get("/settings")
def get_settings_admin(_: str = Depends(require_admin)) -> dict:
    with _db.SessionLocal() as s:
        rows = s.execute(select(Setting.key, Setting.value)).all()
    db_values = {r.key: r.value for r in rows}
    items = [
        {
            "key": m["key"],
            "label": m["label"],
            "desc": m["desc"],
            "kind": m["kind"],
            "default": m["default"],
            "hint": m["hint"],
            "value": typed_setting_value(db_values.get(m["key"]), m["kind"]),
        }
        for m in SETTING_META
    ]
    return {"items": items}


class SettingsIn(BaseModel):
    values: dict[str, object]


@router.put("/settings")
def update_settings_admin(body: SettingsIn, _: str = Depends(require_admin)) -> dict:
    now = datetime.utcnow()
    errors: list[str] = []
    with _db.SessionLocal() as s:
        for key, raw in body.values.items():
            if key not in SETTING_KEYS:
                continue  # 忽略未知 key
            try:
                parsed = parse_setting_input(raw, SETTING_KIND[key])
            except ValueError as e:
                errors.append(f"{key}: {e}")
                continue
            s.execute(
                update(Setting)
                .where(Setting.key == key)
                .values(value=json.dumps(parsed, ensure_ascii=False), updated_at=now)
            )
        if not errors:
            s.commit()
        else:
            s.rollback()
    settings_cache.invalidate()
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})
    return {"ok": True}


# ---- tags -----------------------------------------------------------------


_TAG_VALUE_RE = re.compile(r"^[0-9A-Za-z]{1,8}$")


@router.get("/tags")
def list_tags_admin(_: str = Depends(require_admin)) -> dict:
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(
                Tag.value, Tag.label, Tag.icon_url, Tag.sort, Tag.enabled,
                Tag.proposer_uid, Tag.proposed_at,
            ).order_by(Tag.enabled.desc(), Tag.sort, Tag.proposed_at)
        ).all()
        pending_stats: dict[str, dict[str, int]] = {}
        for r in rows:
            if r.enabled:
                continue
            stat_row = s.execute(
                text(
                    "SELECT COUNT(DISTINCT barrage_id) AS bcnt, COUNT(*) AS vcnt "
                    "FROM barrage_tag_vote WHERE tag_value=:t"
                ),
                {"t": r.value},
            ).mappings().one()
            pending_stats[r.value] = {
                "barrage_count": int(stat_row["bcnt"] or 0),
                "vote_count": int(stat_row["vcnt"] or 0),
            }
        proposer_uids = [r.proposer_uid for r in rows if r.proposer_uid]
        proposer_nicks: dict[str, str] = {}
        if proposer_uids:
            for u, n in s.execute(
                select(User.uid, User.nickname).where(User.uid.in_(proposer_uids))
            ).all():
                if n:
                    proposer_nicks[u] = n
    return {
        "vote_threshold": vote_threshold(),
        "tags": [
            {
                "value": r.value,
                "label": r.label,
                "icon_url": r.icon_url,
                "sort": r.sort,
                "enabled": bool(r.enabled),
                "proposer_uid": r.proposer_uid,
                "proposer_nick": proposer_nicks.get(r.proposer_uid) if r.proposer_uid else None,
                "proposed_at": _iso(r.proposed_at),
                "pending": (None if r.enabled else pending_stats.get(r.value)),
            }
            for r in rows
        ],
    }


class TagCreateIn(BaseModel):
    label: str
    icon_url: str = ""
    sort: int = 0
    value: str = ""  # 可空：留空时服务端自动分配自增内部 id（不展示给用户）


def _next_tag_value(s) -> str:
    """生成服务端自有的自增数字 value（纯数字串，与 tags CSV / LIKE 搜索兼容）。"""
    used = s.execute(select(Tag.value)).scalars().all()
    nums = [int(v) for v in used if v.isdigit()]
    return str((max(nums) + 1) if nums else 1)


@router.post("/tags", status_code=201)
def create_tag_admin(body: TagCreateIn, _: str = Depends(require_admin)) -> dict:
    label = body.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="标签名不能为空")
    with _db.SessionLocal() as s:
        value = body.value.strip()
        if value:
            if not _TAG_VALUE_RE.match(value):
                raise HTTPException(status_code=400, detail="tag value 必须是 1-8 位字母或数字")
            if s.get(Tag, value):
                raise HTTPException(status_code=409, detail="tag 已存在")
        else:
            value = _next_tag_value(s)
        s.add(Tag(
            value=value, label=label,
            icon_url=body.icon_url or None, sort=body.sort, enabled=True,
        ))
        s.commit()
    return {"ok": True, "value": value}


class TagUpdateIn(BaseModel):
    label: str
    icon_url: str = ""
    sort: int = 0
    enabled: bool = True


@router.patch("/tags/{value}")
def update_tag_admin(value: str, body: TagUpdateIn, _: str = Depends(require_admin)) -> dict:
    with _db.SessionLocal() as s:
        row = s.get(Tag, value)
        if not row:
            raise HTTPException(status_code=404, detail="tag 不存在")
        row.label = body.label
        row.icon_url = body.icon_url or None
        row.sort = body.sort
        row.enabled = body.enabled
        s.commit()
    return {"ok": True}


@router.delete("/tags/{value}")
def delete_tag_admin(value: str, _: str = Depends(require_admin)) -> dict:
    with _db.SessionLocal() as s:
        row = s.get(Tag, value)
        if not row:
            raise HTTPException(status_code=404, detail="tag 不存在")
        s.execute(delete(BarrageTagVote).where(BarrageTagVote.tag_value == value))
        s.delete(row)
        s.commit()
    return {"ok": True}


@router.post("/tags/{value}/approve")
def approve_tag_admin(value: str, _: str = Depends(require_admin)) -> dict:
    """批准候选 tag：enabled=False → True，并对已有投票回溯结算。"""
    with _db.SessionLocal() as s:
        row = s.get(Tag, value)
        if not row:
            raise HTTPException(status_code=404, detail="tag 不存在")
        settled = 0
        if not row.enabled:
            row.enabled = True
            settled = settle_all_for_tag(s, value)
            s.commit()
    return {"ok": True, "settled": settled}


# ---- pending --------------------------------------------------------------


@router.get("/pending")
def list_pending_admin(_: str = Depends(require_admin)) -> dict:
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(Barrage)
            .where(Barrage.status == "pending")
            .order_by(desc(Barrage.submit_time))
            .limit(200)
        ).scalars().all()

        uids = [r.submitter_uid for r in rows if r.submitter_uid]
        users: dict[str, User] = {}
        if uids:
            for u in s.execute(select(User).where(User.uid.in_(set(uids)))).scalars().all():
                users[u.uid] = u

        items: list[dict] = []
        for r in rows:
            user = users.get(r.submitter_uid) if r.submitter_uid else None
            recent: list[dict] = []
            if r.submitter_uid:
                recent_rows = s.execute(
                    select(RawDanmaku.ts, RawDanmaku.content_raw)
                    .where(RawDanmaku.uid == r.submitter_uid)
                    .order_by(desc(RawDanmaku.ts))
                    .limit(5)
                ).all()
                recent = [{"ts": _iso(rr.ts), "content": rr.content_raw} for rr in recent_rows]
            items.append({
                "id": r.id,
                "content": r.content,
                "tags": r.tags,
                "submit_time": _iso(r.submit_time),
                "review_reason": r.review_reason,
                "submitter": (
                    {
                        "uid": user.uid,
                        "nickname": user.nickname,
                        "avatar": avatar_url(user.avatar),
                        "last_seen": _iso(user.last_seen),
                    }
                    if user else None
                ),
                "recent_danmaku": recent,
            })
    return {"items": items}


class ApproveIn(BaseModel):
    tags: str = ""


@router.post("/pending/{barrage_id}/approve")
def approve_pending_admin(
    barrage_id: int, body: ApproveIn, _: str = Depends(require_admin)
) -> dict:
    with _db.SessionLocal() as s:
        row = s.get(Barrage, barrage_id)
        if not row:
            raise HTTPException(status_code=404, detail="barrage 不存在")
        if body.tags:
            row.tags = body.tags
        row.status = "active"
        s.commit()
    return {"ok": True}


@router.post("/pending/{barrage_id}/reject")
def reject_pending_admin(barrage_id: int, _: str = Depends(require_admin)) -> dict:
    with _db.SessionLocal() as s:
        row = s.get(Barrage, barrage_id)
        if not row:
            raise HTTPException(status_code=404, detail="barrage 不存在")
        row.status = "deleted"
        s.commit()
    return {"ok": True}


# ---- reports --------------------------------------------------------------


@router.get("/reports")
def list_reports_admin(_: str = Depends(require_admin)) -> dict:
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
    return {
        "items": [
            {
                "id": r["id"],
                "content": r["content"],
                "tags": r["tags"],
                "cnt": r["cnt"],
                "report_cnt": r["report_cnt"],
                "status": r["status"],
                "submit_time": _iso(r["submit_time"]),
                "last_report": _iso(r["last_report"]),
            }
            for r in rows
        ]
    }


@router.post("/reports/{barrage_id}/dismiss")
def dismiss_reports_admin(barrage_id: int, _: str = Depends(require_admin)) -> dict:
    """「这条没问题」：清零 report_cnt 并删除该条所有反馈记录；投稿保持 active。"""
    with _db.SessionLocal() as s:
        row = s.get(Barrage, barrage_id)
        if not row:
            raise HTTPException(status_code=404, detail="barrage 不存在")
        s.execute(delete(BarrageReport).where(BarrageReport.barrage_id == barrage_id))
        row.report_cnt = 0
        s.commit()
    return {"ok": True}


# ---- barrage（全部投稿管理）----------------------------------------------


@router.get("/barrage")
def list_barrage_admin(
    q: str = "",
    sort: Literal["new", "hot"] = "new",
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    _: str = Depends(require_admin),
) -> dict:
    """全部已上架烂梗：复用公开搜索（FTS/LIKE + 分页），附 report_cnt 供管理与下架。"""
    from ..search import search_barrage

    res = search_barrage(q=q or None, tags=None, sort=sort, page=page, size=size)
    items = res["list"]
    if items:
        ids = [it["id"] for it in items]
        with _db.SessionLocal() as s:
            rc = {
                r.id: r.report_cnt
                for r in s.execute(
                    select(Barrage.id, Barrage.report_cnt).where(Barrage.id.in_(ids))
                ).all()
            }
        for it in items:
            it["report_cnt"] = rc.get(it["id"], 0)
    return {
        "items": items,
        "total": res["total"],
        "last_page": res["last_page"],
        "page": page,
    }


class BarrageEditIn(BaseModel):
    content: str
    tags: list[str] = []


@router.patch("/barrage/{barrage_id}")
def edit_barrage_admin(
    barrage_id: int, body: BarrageEditIn, _: str = Depends(require_admin)
) -> dict:
    """编辑一条投稿的正文与标签。

    正文改动按投稿同款 `normalize()` 重算 `content_norm`（唯一键）并查重：
    与另一条 active/任意 投稿撞库 → 409。tags 接收 value 列表，存为去重排序后的 CSV。
    """
    from ..normalize import normalize

    content = body.content.strip()
    min_len = int(settings_cache.get("barrage_min_length", 4) or 4)
    max_len = int(settings_cache.get("barrage_max_length", 255) or 255)
    if len(content) < min_len or len(content) > max_len:
        raise HTTPException(status_code=400, detail=f"正文长度需在 {min_len}–{max_len} 字之间")
    content_norm = normalize(content)
    if not content_norm:
        raise HTTPException(status_code=400, detail="正文归一化后为空")
    tags_csv = ",".join(sorted({t.strip() for t in body.tags if t.strip()}))
    with _db.SessionLocal() as s:
        row = s.get(Barrage, barrage_id)
        if not row:
            raise HTTPException(status_code=404, detail="barrage 不存在")
        clash = s.execute(
            select(Barrage.id).where(
                Barrage.content_norm == content_norm, Barrage.id != barrage_id
            )
        ).first()
        if clash:
            raise HTTPException(status_code=409, detail="正文与另一条烂梗重复")
        row.content = content
        row.content_norm = content_norm
        row.tags = tags_csv
        s.commit()
    return {"ok": True}


@router.post("/barrage/{barrage_id}/delete")
def delete_barrage_admin(barrage_id: int, _: str = Depends(require_admin)) -> dict:
    """下架（软删）一条投稿：status → deleted，进回收站、可恢复。供「全部烂梗」与「反馈」页共用。"""
    with _db.SessionLocal() as s:
        row = s.get(Barrage, barrage_id)
        if not row:
            raise HTTPException(status_code=404, detail="barrage 不存在")
        row.status = "deleted"
        s.commit()
    return {"ok": True}


# ---- trash ----------------------------------------------------------------


@router.get("/trash")
def list_trash_admin(_: str = Depends(require_admin)) -> dict:
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(Barrage)
            .where(Barrage.status == "deleted")
            .order_by(desc(Barrage.submit_time))
            .limit(200)
        ).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "content": r.content,
                "tags": r.tags,
                "cnt": r.cnt,
                "report_cnt": r.report_cnt,
                "submit_time": _iso(r.submit_time),
            }
            for r in rows
        ]
    }


@router.post("/trash/{barrage_id}/restore")
def restore_trash_admin(barrage_id: int, _: str = Depends(require_admin)) -> dict:
    with _db.SessionLocal() as s:
        row = s.get(Barrage, barrage_id)
        if not row:
            raise HTTPException(status_code=404, detail="barrage 不存在")
        row.status = "active"
        s.commit()
    return {"ok": True}


@router.post("/trash/{barrage_id}/purge")
def purge_trash_admin(barrage_id: int, _: str = Depends(require_admin)) -> dict:
    with _db.SessionLocal() as s:
        s.execute(delete(BarrageReport).where(BarrageReport.barrage_id == barrage_id))
        s.execute(delete(Barrage).where(Barrage.id == barrage_id))
        s.commit()
    return {"ok": True}


# ---- summary（工作台待办摘要）--------------------------------------------


@router.get("/summary")
def summary_admin(_: str = Depends(require_admin)) -> dict:
    """轻量待办摘要：给工作台卡片与导航角标用（待审数 / 待处理举报 / 烂梗库总数）。"""
    with _db.SessionLocal() as s:
        pending = s.execute(
            select(func.count(Barrage.id)).where(Barrage.status == "pending")
        ).scalar_one()
        open_reports = s.execute(
            select(func.count(Barrage.id)).where(Barrage.report_cnt > 0)
        ).scalar_one()
        library_total = s.execute(
            select(func.count(Barrage.id)).where(Barrage.status == "active")
        ).scalar_one()
    return {"pending": pending, "open_reports": open_reports, "library_total": library_total}


# ---- live_hot -------------------------------------------------------------


@router.get("/live-hot")
def list_live_hot_admin(
    filtered: bool = Query(False), _: str = Depends(require_admin)
) -> dict:
    where = "is_filtered=1" if filtered else "1=1"
    sql = text(
        "SELECT id, content_sample, live_date, send_cnt, unique_sender_cnt, last_seen, is_filtered "
        f"FROM daily_hot WHERE {where} "
        "ORDER BY live_date DESC, send_cnt DESC LIMIT 200"
    )
    with _db.SessionLocal() as s:
        rows = s.execute(sql).mappings().all()
    return {
        "filtered": filtered,
        "items": [
            {
                "id": r["id"],
                "content_sample": r["content_sample"],
                "live_date": r["live_date"],
                "send_cnt": r["send_cnt"],
                "unique_sender_cnt": r["unique_sender_cnt"],
                "last_seen": _iso(r["last_seen"]),
                "is_filtered": bool(r["is_filtered"]),
            }
            for r in rows
        ],
    }


@router.get("/live-hot/{live_hot_id}")
def live_hot_detail_admin(live_hot_id: int, _: str = Depends(require_admin)) -> dict:
    with _db.SessionLocal() as s:
        hot = s.get(DailyHot, live_hot_id)
        if not hot:
            raise HTTPException(status_code=404, detail="live_hot 不存在")
        sql = text(
            "SELECT uid, nickname, ts, content_raw FROM raw_danmaku "
            "WHERE content_norm = :cn ORDER BY ts DESC LIMIT 500"
        )
        raws = s.execute(sql, {"cn": hot.content_norm}).mappings().all()
        uid_cnt: dict[str, int] = {}
        for r in raws:
            if r["uid"]:
                uid_cnt[r["uid"]] = uid_cnt.get(r["uid"], 0) + 1
        top_uids = sorted(uid_cnt.items(), key=lambda x: -x[1])[:30]
        hot_payload = {
            "id": hot.id,
            "live_date": hot.live_date,
            "content_norm": hot.content_norm,
            "content_sample": hot.content_sample,
            "send_cnt": hot.send_cnt,
            "unique_sender_cnt": hot.unique_sender_cnt,
            "first_seen": _iso(hot.first_seen),
            "last_seen": _iso(hot.last_seen),
            "is_filtered": bool(hot.is_filtered),
        }
    return {
        "hot": hot_payload,
        "raws": [
            {"uid": r["uid"], "nickname": r["nickname"], "ts": _iso(r["ts"]), "content": r["content_raw"]}
            for r in raws
        ],
        "top_uids": [{"uid": u, "count": c} for u, c in top_uids],
    }


@router.post("/live-hot/recompute")
def live_hot_recompute_admin(_: str = Depends(require_admin)) -> dict:
    """重归一化所有 raw_danmaku.content_norm 后重建当日 daily_hot。"""
    from ..normalize import normalize
    from ..ingest.aggregator import normalized_suffix_strips, normalized_cut_markers

    settings_cache.invalidate()
    suffixes = normalized_suffix_strips()
    cut_markers = normalized_cut_markers()
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(RawDanmaku.id, RawDanmaku.content_raw, RawDanmaku.content_norm)
        ).all()
        n_raw_updated = 0
        for rid, raw, old_norm in rows:
            new_norm = normalize(raw or "", suffixes=suffixes, cut_markers=cut_markers)
            if new_norm != old_norm:
                s.execute(
                    update(RawDanmaku).where(RawDanmaku.id == rid).values(content_norm=new_norm)
                )
                n_raw_updated += 1
        s.commit()
    from ..cron import _recount_sync
    _recount_sync()
    return {"ok": True, "raw_renormalized": n_raw_updated}


@router.post("/live-hot/rescan")
def live_hot_rescan_admin(_: str = Depends(require_admin)) -> dict:
    """按当前阈值/降噪规则重建当日 daily_hot。"""
    settings_cache.invalidate()
    from ..cron import _recount_sync
    _recount_sync()
    return {"ok": True}


# ---- stats ----------------------------------------------------------------


@router.get("/stats")
def stats_admin(_: str = Depends(require_admin)) -> dict:
    now = datetime.utcnow()
    h24 = now - timedelta(hours=24)
    with _db.SessionLocal() as s:
        raw_24h = s.execute(
            select(func.count(RawDanmaku.id)).where(RawDanmaku.ts >= h24)
        ).scalar_one()
        submit_24h = s.execute(
            select(func.count(Barrage.id)).where(Barrage.submit_time >= h24)
        ).scalar_one()
        copy_total = s.execute(select(func.sum(Barrage.cnt))).scalar() or 0
        live_hot_total = s.execute(select(func.count(DailyHot.id))).scalar_one()
        pending_total = s.execute(
            select(func.count(Barrage.id)).where(Barrage.status == "pending")
        ).scalar_one()
        deleted_total = s.execute(
            select(func.count(Barrage.id)).where(Barrage.status == "deleted")
        ).scalar_one()
        report_24h = s.execute(
            select(func.count(BarrageReport.id)).where(BarrageReport.ts >= h24)
        ).scalar_one()
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

        # 给每个 IP 哈希回填「这个 IP 背后是谁投的」：关联 user 拿斗鱼昵称/头像；
        # submitter_uid 为空的算匿名。一个 IP 可能对应多个署名 + 匿名混合。
        ip_hashes = [r[0] for r in top_ip_rows]
        submitters_by_ip: dict[str, list[dict]] = {}
        anon_by_ip: dict[str, bool] = {}
        if ip_hashes:
            sub_sql = text(
                "SELECT b.submitter_ip_hash AS iph, b.submitter_uid AS uid, "
                "       u.nickname AS nickname, u.avatar AS avatar "
                "FROM barrage b LEFT JOIN user u ON u.uid = b.submitter_uid "
                "WHERE b.submit_time >= :h24 AND b.submitter_ip_hash IN :ips"
            ).bindparams(bindparam("ips", expanding=True))
            for r in s.execute(sub_sql, {"h24": h24, "ips": ip_hashes}).mappings().all():
                iph = r["iph"]
                if r["uid"] and r["nickname"]:
                    lst = submitters_by_ip.setdefault(iph, [])
                    if not any(x["nickname"] == r["nickname"] for x in lst):
                        lst.append({"nickname": r["nickname"], "avatar": avatar_url(r["avatar"])})
                elif not r["uid"]:
                    anon_by_ip[iph] = True
    return {
        "raw_24h": raw_24h,
        "submit_24h": submit_24h,
        "copy_total": copy_total,
        "live_hot_total": live_hot_total,
        "pending_total": pending_total,
        "deleted_total": deleted_total,
        "report_24h": report_24h,
        "top_ip": [
            {
                "ip_hash": r[0],
                "count": r[1],
                "submitters": submitters_by_ip.get(r[0], []),
                "anon": anon_by_ip.get(r[0], False),
            }
            for r in top_ip_rows
        ],
    }
