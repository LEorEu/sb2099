"""/api/* JSON 路由 — 切片 R 只读 + 切片 W 写入。/admin 留给 A。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from .. import __version__ as sb_version
from .. import db as _db
from ..models import Barrage, BarrageReport, DailyHot, Tag
from ..normalize import normalize
from ..ratelimit import extract_ip, ip_hash, limiter, rate_for
from ..search import search_barrage
from ..settings import settings_cache
from ..submission import evaluate

router = APIRouter(prefix="/api")


# ---- read-only (slice R) -------------------------------------------------


@router.get("/tags")
def list_tags() -> dict:
    with _db.SessionLocal() as s:
        rows = s.execute(
            select(Tag.value, Tag.label, Tag.icon_url, Tag.sort)
            .where(Tag.enabled.is_(True))
            .order_by(Tag.sort)
        ).all()
    return {
        "data": [
            {"value": r.value, "label": r.label, "icon_url": r.icon_url, "sort": r.sort}
            for r in rows
        ]
    }


def _live_rows(window: str):
    from datetime import datetime, timezone
    from ..live_day import current_live_window
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    live_date, _ = current_live_window(now)
    if window == "day":
        sql = text(
            "SELECT id, content_sample, send_cnt, unique_sender_cnt AS unique_senders, last_seen "
            "FROM daily_hot WHERE live_date = :d AND is_filtered = 0 "
            "ORDER BY send_cnt DESC, last_seen DESC LIMIT 10"
        )
        params = {"d": live_date.isoformat()}
    else:
        from datetime import timedelta
        wk_start = (live_date - timedelta(days=6)).isoformat()
        sql = text(
            "SELECT "
            "  (SELECT d2.id FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "     AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS id, "
            "  (SELECT d2.content_sample FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "     AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS content_sample, "
            "  SUM(d.send_cnt) AS send_cnt, MAX(d.unique_sender_cnt) AS unique_senders, "
            "  MAX(d.last_seen) AS last_seen "
            "FROM daily_hot d WHERE d.live_date >= :wk AND d.is_filtered = 0 "
            "GROUP BY d.content_norm ORDER BY send_cnt DESC, last_seen DESC LIMIT 50"
        )
        params = {"wk": wk_start}
    with _db.SessionLocal() as s:
        return s.execute(sql, params).mappings().all()


@router.get("/live")
def get_live(window: Literal["day", "week"] = "day") -> dict:
    rows = _live_rows(window)
    return {
        "window": window,
        "data": [
            {
                "id": r["id"],
                "content_sample": r["content_sample"],
                "send_cnt": int(r["send_cnt"] or 0),
                "unique_senders": int(r["unique_senders"] or 0),
                "last_seen": (
                    r["last_seen"].isoformat()
                    if hasattr(r["last_seen"], "isoformat")
                    else (str(r["last_seen"]) if r["last_seen"] else None)
                ),
            }
            for r in rows
        ],
    }


@router.get("/barrage")
def get_barrage(
    q: str | None = None,
    tag: str | None = Query(None, description="CSV: 00,02"),
    sort: Literal["new", "hot"] = "new",
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    tags = [t for t in tag.split(",") if t] if tag else None
    return {"data": search_barrage(q=q, tags=tags, sort=sort, page=page, size=size)}


@router.get("/random")
def get_random() -> dict:
    with _db.SessionLocal() as s:
        row = s.execute(
            select(Barrage.id, Barrage.content, Barrage.tags, Barrage.cnt, Barrage.submit_time)
            .where(Barrage.status == "active")
            .order_by(func.random())
            .limit(1)
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="empty barrage library")
    return {
        "data": {
            "id": row.id,
            "content": row.content,
            "tags": row.tags,
            "cnt": row.cnt,
            "submit_time": row.submit_time.isoformat() if row.submit_time else None,
        }
    }


@router.get("/userscript/version")
def get_userscript_version() -> dict:
    return {"version": sb_version}


# ---- write (slice W) -----------------------------------------------------


class SubmitIn(BaseModel):
    content: str
    tags: list[str] = Field(min_length=1)

    @field_validator("tags")
    @classmethod
    def _tags_nonempty(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip() for t in v if t and t.strip()]
        if not cleaned:
            raise ValueError("at least one tag required")
        return cleaned


def _barrage_to_dict(row) -> dict:
    return {
        "id": row.id,
        "content": row.content,
        "tags": row.tags,
        "cnt": row.cnt,
        "submit_time": row.submit_time.isoformat() if row.submit_time else None,
        "status": row.status,
    }


def _enabled_tag_values() -> set[str]:
    with _db.SessionLocal() as s:
        return set(
            s.execute(select(Tag.value).where(Tag.enabled.is_(True))).scalars().all()
        )


@router.post("/barrage", status_code=201)
@limiter.limit(lambda: rate_for("ratelimit_submit_per_hour_per_ip", 5))
def submit_barrage(request: Request, body: SubmitIn) -> dict:
    # 长度
    min_len = int(settings_cache.get("barrage_min_length", 4) or 4)
    max_len = int(settings_cache.get("barrage_max_length", 255) or 255)
    content = body.content.strip()
    if len(content) < min_len or len(content) > max_len:
        raise HTTPException(
            status_code=400,
            detail=f"content length must be between {min_len} and {max_len}",
        )

    # tags 必须全部存在且 enabled
    enabled = _enabled_tag_values()
    invalid = [t for t in body.tags if t not in enabled]
    if invalid:
        raise HTTPException(status_code=400, detail=f"unknown tags: {invalid}")

    content_norm = normalize(content)
    if not content_norm:
        raise HTTPException(status_code=400, detail="content normalizes to empty")

    # 撞库 → 409
    with _db.SessionLocal() as s:
        existing = s.execute(
            select(Barrage).where(Barrage.content_norm == content_norm)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail={"message": "duplicate", "existing": _barrage_to_dict(existing)},
            )

    # submission_review_rules
    rules = settings_cache.get("submission_review_rules", []) or []
    verdict = evaluate(content, rules)
    if verdict.action == "block":
        raise HTTPException(
            status_code=422,
            detail={"message": "blocked", "matched_pattern": verdict.matched_pattern},
        )
    status = "pending" if verdict.action == "pending" else "active"

    row_data = {
        "content": content,
        "content_norm": content_norm,
        "tags": ",".join(sorted(set(body.tags))),
        "source": "user",
        "submitter_ip_hash": ip_hash(extract_ip(request)),
        "submit_time": datetime.utcnow(),
        "cnt": 0,
        "report_cnt": 0,
        "status": status,
    }
    with _db.SessionLocal() as s:
        try:
            new = Barrage(**row_data)
            s.add(new)
            s.commit()
            s.refresh(new)
        except IntegrityError:
            # 并发投稿撞库
            s.rollback()
            existing = s.execute(
                select(Barrage).where(Barrage.content_norm == content_norm)
            ).scalar_one()
            raise HTTPException(
                status_code=409,
                detail={"message": "duplicate", "existing": _barrage_to_dict(existing)},
            )
        return {"data": _barrage_to_dict(new)}


class CopyIn(BaseModel):
    source: Literal["barrage", "live_hot"]
    id: int


@router.post("/copy", status_code=200)
@limiter.limit(lambda: rate_for("ratelimit_copy_per_hour_per_ip", 200))
def copy_one(request: Request, body: CopyIn) -> dict:
    with _db.SessionLocal() as s:
        if body.source == "barrage":
            res = s.execute(
                update(Barrage)
                .where(Barrage.id == body.id, Barrage.status == "active")
                .values(cnt=Barrage.cnt + 1)
            )
            s.commit()
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="barrage not found")
            return {"data": {"source": "barrage", "id": body.id}}
        # 公开 API 合约：source/字段名沿用 "live_hot"，底层实为 daily_hot
        else:
            res = s.execute(
                update(DailyHot)
                .where(DailyHot.id == body.id)
                .values(page_copy_cnt=DailyHot.page_copy_cnt + 1)
            )
            s.commit()
            if res.rowcount == 0:
                raise HTTPException(status_code=404, detail="live_hot not found")
            return {"data": {"source": "live_hot", "id": body.id}}


class ReportIn(BaseModel):
    id: int


@router.post("/barrage/report", status_code=200)
@limiter.limit(lambda: rate_for("ratelimit_report_per_hour_per_ip", 60))
def report_barrage(request: Request, body: ReportIn) -> dict:
    iph = ip_hash(extract_ip(request))
    with _db.SessionLocal() as s:
        row = s.execute(
            select(Barrage).where(Barrage.id == body.id, Barrage.status == "active")
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="barrage not found")
        rep = BarrageReport(barrage_id=body.id, ip_hash=iph, ts=datetime.utcnow())
        s.add(rep)
        try:
            s.flush()
            row.report_cnt = row.report_cnt + 1
            s.commit()
            return {"data": {"id": body.id, "report_cnt": row.report_cnt}}
        except IntegrityError:
            # 同 IP 重复举报
            s.rollback()
            cur = s.execute(
                select(Barrage.report_cnt).where(Barrage.id == body.id)
            ).scalar_one()
            return {"data": {"id": body.id, "report_cnt": cur, "duplicate": True}}


class PromoteIn(BaseModel):
    live_hot_id: int
    tags: list[str] = Field(min_length=1)


@router.post("/promote", status_code=201)
@limiter.limit(lambda: rate_for("ratelimit_promote_per_hour_per_ip", 5))
def promote(request: Request, body: PromoteIn) -> dict:
    enabled = _enabled_tag_values()
    invalid = [t for t in body.tags if t not in enabled]
    if invalid:
        raise HTTPException(status_code=400, detail=f"unknown tags: {invalid}")

    with _db.SessionLocal() as s:
        # 公开 API 合约：source/字段名沿用 "live_hot"，底层实为 daily_hot
        hot = s.execute(
            select(DailyHot).where(DailyHot.id == body.live_hot_id)
        ).scalar_one_or_none()
        if hot is None:
            raise HTTPException(status_code=404, detail="live_hot not found")
        content = hot.content_sample
        content_norm = hot.content_norm
        existing = s.execute(
            select(Barrage).where(Barrage.content_norm == content_norm)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail={"message": "already in barrage", "existing": _barrage_to_dict(existing)},
            )

        # 也走 submission_review_rules（提升路径不应绕过审核）
        rules = settings_cache.get("submission_review_rules", []) or []
        verdict = evaluate(content, rules)
        if verdict.action == "block":
            raise HTTPException(
                status_code=422,
                detail={"message": "blocked", "matched_pattern": verdict.matched_pattern},
            )
        status = "pending" if verdict.action == "pending" else "active"

        new = Barrage(
            content=content,
            content_norm=content_norm,
            tags=",".join(sorted(set(body.tags))),
            source="promoted",
            submitter_ip_hash=ip_hash(extract_ip(request)),
            submit_time=datetime.utcnow(),
            cnt=0,
            report_cnt=0,
            status=status,
        )
        s.add(new)
        try:
            s.commit()
            s.refresh(new)
        except IntegrityError:
            s.rollback()
            raise HTTPException(status_code=409, detail="duplicate (race)")
        return {"data": _barrage_to_dict(new)}
