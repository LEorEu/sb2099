"""/api/* JSON 路由 — 切片 R 只读 + 切片 W 写入。/admin 留给 A。"""
from __future__ import annotations

import hashlib
import hmac
import re
import time
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from .. import __version__ as sb_version
from .. import db as _db
from ..config import get_settings
from ..models import Barrage, BarrageReport, BarrageTagVote, DailyHot, Tag, User
from ..normalize import normalize
from ..ratelimit import extract_ip, ip_hash, limiter, rate_for
from ..search import search_barrage
from ..settings import settings_cache
from ..submission import evaluate, review_uid
from ..tag_voting import settle_tag, vote_count, vote_threshold

router = APIRouter(prefix="/api")


# ---- 撤回窗口的 HMAC cookie 工具 -----------------------------------------


def _hmac_token(barrage_id: int, ip_h: str, expires_at: int) -> str:
    """token = base16(HMAC-SHA256(salt, "<id>.<ip>.<exp>")) + ".<exp>"

    payload 含 expires_at；ip_hash 也参与 HMAC，防止 cookie 被换 IP 复用。
    """
    salt = get_settings().SB2099_IP_SALT.encode()
    msg = f"{barrage_id}.{ip_h}.{expires_at}".encode()
    sig = hmac.new(salt, msg, hashlib.sha256).hexdigest()
    return f"{sig}.{expires_at}"


def _hmac_verify(token: str, barrage_id: int, ip_h: str) -> int | None:
    """验证 token 并返回 expires_at；任何环节失败返回 None。"""
    if not token or "." not in token:
        return None
    sig, _, exp_str = token.partition(".")
    try:
        expires_at = int(exp_str)
    except ValueError:
        return None
    expected = _hmac_token(barrage_id, ip_h, expires_at).split(".", 1)[0]
    if not hmac.compare_digest(sig, expected):
        return None
    return expires_at


def _withdraw_window_seconds() -> int:
    try:
        return max(1, int(settings_cache.get("submission_withdraw_window_seconds", 60) or 60))
    except (TypeError, ValueError):
        return 60


def _set_recent_cookie(response: Response, barrage_id: int, ip_h: str) -> None:
    window = _withdraw_window_seconds()
    expires_at = int(time.time()) + window
    token = _hmac_token(barrage_id, ip_h, expires_at)
    response.set_cookie(
        key=f"sb_recent_{barrage_id}",
        value=token,
        max_age=window,
        httponly=True,
        samesite="strict",
        path="/",
    )


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
            "SELECT d.id, d.content_sample, d.send_cnt, "
            "  d.unique_sender_cnt AS unique_senders, d.last_seen, "
            "  b.id AS barrage_id, b.tags AS barrage_tags "
            "FROM daily_hot d "
            "LEFT JOIN barrage b ON b.content_norm = d.content_norm AND b.status='active' "
            "WHERE d.live_date = :d AND d.is_filtered = 0 "
            "ORDER BY d.send_cnt DESC, d.last_seen DESC LIMIT 10"
        )
        params = {"d": live_date.isoformat()}
    else:
        from datetime import timedelta
        wk_start = (live_date - timedelta(days=6)).isoformat()
        sql = text(
            "SELECT t.*, b.id AS barrage_id, b.tags AS barrage_tags FROM ("
            "  SELECT d.content_norm AS content_norm, "
            "    (SELECT d2.id FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "       AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS id, "
            "    (SELECT d2.content_sample FROM daily_hot d2 WHERE d2.content_norm=d.content_norm "
            "       AND d2.live_date>=:wk ORDER BY d2.live_date DESC LIMIT 1) AS content_sample, "
            "    SUM(d.send_cnt) AS send_cnt, MAX(d.unique_sender_cnt) AS unique_senders, "
            "    MAX(d.last_seen) AS last_seen "
            "  FROM daily_hot d WHERE d.live_date >= :wk AND d.is_filtered = 0 "
            "  GROUP BY d.content_norm "
            "  ORDER BY send_cnt DESC, last_seen DESC LIMIT 50"
            ") t LEFT JOIN barrage b ON b.content_norm = t.content_norm AND b.status='active'"
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
                "in_library": r["barrage_id"] is not None,
                "barrage_tags": r["barrage_tags"],
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


@router.get("/users/search")
@limiter.limit(lambda: rate_for("ratelimit_copy_per_hour_per_ip", 200))
def search_users(request: Request, q: str = "", limit: int = 10) -> dict:
    """昵称模糊搜索；q 全数字时按 uid 前缀。

    返回上限 10 条，按 last_seen 倒序。**只返 nickname + avatar，不返 uid**——
    avatar 是斗鱼 CDN 完整 URL；前端获取 uid 走另一路（投稿请求里带 uid 时由该端点
    返回的列表项自己附带，下面 results 里仍含 uid 字段供前端选中后回传，但不公开列举）。

    要求 q > 2 字符；空 / 单双字 q 一律返回空列表，避免被批量拉名册。
    """
    from ..users import avatar_url

    q = (q or "").strip()
    if len(q) <= 2:
        return {"results": []}
    limit = max(1, min(int(limit or 10), 10))

    with _db.SessionLocal() as s:
        if q.isdigit():
            stmt = (
                select(User.uid, User.nickname, User.avatar)
                .where(User.uid.like(f"{q}%"))
                .order_by(User.last_seen.desc())
                .limit(limit)
            )
        else:
            stmt = (
                select(User.uid, User.nickname, User.avatar)
                .where(User.nickname.like(f"%{q}%"))
                .order_by(User.last_seen.desc())
                .limit(limit)
            )
        rows = s.execute(stmt).all()

    return {
        "results": [
            {"uid": r.uid, "nickname": r.nickname, "avatar": avatar_url(r.avatar)}
            for r in rows
        ]
    }


@router.get("/random")
def get_random() -> dict:
    from ..users import avatar_url

    with _db.SessionLocal() as s:
        row = s.execute(
            select(
                Barrage.id,
                Barrage.content,
                Barrage.tags,
                Barrage.cnt,
                Barrage.submit_time,
                User.nickname.label("submitter_nickname"),
                User.avatar.label("submitter_avatar"),
            )
            .outerjoin(User, User.uid == Barrage.submitter_uid)
            .where(Barrage.status == "active")
            .order_by(func.random())
            .limit(1)
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="empty barrage library")
    submitter = None
    if row.submitter_nickname:
        submitter = {
            "nickname": row.submitter_nickname,
            "avatar": avatar_url(row.submitter_avatar),
        }
    return {
        "data": {
            "id": row.id,
            "content": row.content,
            "tags": row.tags,
            "cnt": row.cnt,
            "submit_time": row.submit_time.isoformat() if row.submit_time else None,
            "submitter": submitter,
        }
    }


@router.get("/userscript/version")
def get_userscript_version() -> dict:
    return {"version": sb_version}


# ---- write (slice W) -----------------------------------------------------


class SubmitIn(BaseModel):
    content: str
    tags: list[str] = Field(min_length=1)
    submitter_uid: str | None = None  # 可选；NULL=匿名

    @field_validator("tags")
    @classmethod
    def _tags_nonempty(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip() for t in v if t and t.strip()]
        if not cleaned:
            raise ValueError("at least one tag required")
        return cleaned

    @field_validator("submitter_uid")
    @classmethod
    def _uid_clean(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


def _barrage_to_dict(row) -> dict:
    return {
        "id": row.id,
        "content": row.content,
        "tags": row.tags,
        "cnt": row.cnt,
        "submit_time": row.submit_time.isoformat() if row.submit_time else None,
        "status": row.status,
    }


def _resolve_submitter_uid(session, uid: str | None) -> str | None:
    """uid 必须在 user 表里才视为有效；否则当匿名处理（不报错）。"""
    if not uid:
        return None
    found = session.execute(select(User.uid).where(User.uid == uid)).scalar_one_or_none()
    return found


def _enabled_tag_values() -> set[str]:
    with _db.SessionLocal() as s:
        return set(
            s.execute(select(Tag.value).where(Tag.enabled.is_(True))).scalars().all()
        )


@router.post("/barrage", status_code=201)
@limiter.limit(lambda: rate_for("ratelimit_submit_per_hour_per_ip", 5))
def submit_barrage(request: Request, response: Response, body: SubmitIn) -> dict:
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

    # submission_review_rules（内容规则）
    rules = settings_cache.get("submission_review_rules", []) or []
    verdict = evaluate(content, rules)
    if verdict.action == "block":
        raise HTTPException(
            status_code=422,
            detail={"message": "blocked", "matched_pattern": verdict.matched_pattern},
        )

    ip_h = ip_hash(extract_ip(request))
    with _db.SessionLocal() as s:
        # uid 校验 + 防伪探测器
        resolved_uid = _resolve_submitter_uid(s, body.submitter_uid)
        review_reason: str | None = None
        if verdict.action == "pending":
            review_reason = f"content_rule:{verdict.matched_pattern}"
            status = "pending"
        else:
            status = "active"
        if status == "active" and resolved_uid is not None:
            uid_pending, uid_reason = review_uid(s, resolved_uid, ip_h)
            if uid_pending:
                status = "pending"
                review_reason = uid_reason

        row_data = {
            "content": content,
            "content_norm": content_norm,
            "tags": ",".join(sorted(set(body.tags))),
            "source": "user",
            "submitter_ip_hash": ip_h,
            "submitter_uid": resolved_uid,
            "submit_time": datetime.utcnow(),
            "cnt": 0,
            "report_cnt": 0,
            "status": status,
            "review_reason": review_reason,
        }
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
        _set_recent_cookie(response, new.id, ip_h)
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
    submitter_uid: str | None = None

    @field_validator("submitter_uid")
    @classmethod
    def _uid_clean(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


@router.post("/promote", status_code=201)
@limiter.limit(lambda: rate_for("ratelimit_promote_per_hour_per_ip", 5))
def promote(request: Request, response: Response, body: PromoteIn) -> dict:
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

        ip_h = ip_hash(extract_ip(request))
        resolved_uid = _resolve_submitter_uid(s, body.submitter_uid)
        review_reason: str | None = None
        if verdict.action == "pending":
            review_reason = f"content_rule:{verdict.matched_pattern}"
            status = "pending"
        else:
            status = "active"
        if status == "active" and resolved_uid is not None:
            uid_pending, uid_reason = review_uid(s, resolved_uid, ip_h)
            if uid_pending:
                status = "pending"
                review_reason = uid_reason

        new = Barrage(
            content=content,
            content_norm=content_norm,
            tags=",".join(sorted(set(body.tags))),
            source="promoted",
            submitter_ip_hash=ip_h,
            submitter_uid=resolved_uid,
            submit_time=datetime.utcnow(),
            cnt=0,
            report_cnt=0,
            status=status,
            review_reason=review_reason,
        )
        s.add(new)
        try:
            s.commit()
            s.refresh(new)
        except IntegrityError:
            s.rollback()
            raise HTTPException(status_code=409, detail="duplicate (race)")
        _set_recent_cookie(response, new.id, ip_h)
        return {"data": _barrage_to_dict(new)}


_TAG_VALUE_RE = re.compile(r"^[0-9A-Za-z]{1,8}$")


class VoteTagIn(BaseModel):
    tag_value: str
    voter_uid: str | None = None

    @field_validator("tag_value")
    @classmethod
    def _v(cls, v: str) -> str:
        v = (v or "").strip()
        if not _TAG_VALUE_RE.match(v):
            raise ValueError("tag_value must be 1-8 alphanumeric chars")
        return v

    @field_validator("voter_uid")
    @classmethod
    def _u(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


@router.post("/barrage/{barrage_id}/vote-tag")
@limiter.limit(lambda: rate_for("ratelimit_vote_per_hour_per_ip", 60))
def vote_tag(barrage_id: int, request: Request, body: VoteTagIn) -> dict:
    """观众给已发布的 barrage 投 tag 票。

    - tag 必须已在 Tag 表（不限 enabled）；不存在 → 404 提示需走 propose-tag
    - 投票即时记账（PK 冲突静默 = 幂等），返回当前票数 / 阈值
    - tag.enabled=True 时立即结算 → applied 表示这一票推过阈值
    - tag.enabled=False 时计票不结算（admin 审核通过会回溯）
    """
    with _db.SessionLocal() as s:
        b = s.execute(
            select(Barrage).where(Barrage.id == barrage_id, Barrage.status == "active")
        ).scalar_one_or_none()
        if b is None:
            raise HTTPException(status_code=404, detail="barrage not found")
        tag = s.execute(select(Tag).where(Tag.value == body.tag_value)).scalar_one_or_none()
        if tag is None:
            raise HTTPException(
                status_code=404,
                detail={"message": "tag not found", "hint": "use /api/barrage/{id}/propose-tag"},
            )
        ip_h = ip_hash(extract_ip(request))
        resolved_uid = _resolve_submitter_uid(s, body.voter_uid)
        vote = BarrageTagVote(
            barrage_id=barrage_id,
            tag_value=body.tag_value,
            voter_uid=resolved_uid,
            voter_ip_hash=ip_h,
            ts=datetime.utcnow(),
        )
        s.add(vote)
        try:
            s.commit()
        except IntegrityError:
            s.rollback()  # 重复投票，幂等
        applied = False
        if tag.enabled:
            if settle_tag(s, barrage_id, body.tag_value):
                s.commit()
                applied = True
        count = vote_count(s, barrage_id, body.tag_value)
        return {
            "data": {
                "tag": body.tag_value,
                "count": count,
                "threshold": vote_threshold(),
                "applied": applied,
                "pending_approval": not tag.enabled,
            }
        }


class ProposeTagIn(BaseModel):
    value: str = Field(min_length=1, max_length=8)
    label: str = Field(min_length=1, max_length=32)
    voter_uid: str | None = None

    @field_validator("value")
    @classmethod
    def _v(cls, v: str) -> str:
        v = v.strip()
        if not _TAG_VALUE_RE.match(v):
            raise ValueError("value must be 1-8 alphanumeric chars")
        return v

    @field_validator("label")
    @classmethod
    def _l(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("label required")
        return v

    @field_validator("voter_uid")
    @classmethod
    def _u(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


@router.post("/barrage/{barrage_id}/propose-tag", status_code=201)
@limiter.limit(lambda: rate_for("ratelimit_propose_per_hour_per_ip", 10))
def propose_tag(barrage_id: int, request: Request, body: ProposeTagIn) -> dict:
    """提议新 tag 并自动给当前 barrage 投一票。

    - value 已存在且 enabled=True → 409（直接走 vote-tag）
    - value 已存在且 enabled=False → 复用现有候选，给 barrage 投一票即可
    - value 不存在 → 创建 Tag(enabled=False) + 给 barrage 投一票
    """
    with _db.SessionLocal() as s:
        b = s.execute(
            select(Barrage).where(Barrage.id == barrage_id, Barrage.status == "active")
        ).scalar_one_or_none()
        if b is None:
            raise HTTPException(status_code=404, detail="barrage not found")
        ip_h = ip_hash(extract_ip(request))
        resolved_uid = _resolve_submitter_uid(s, body.voter_uid)
        existing = s.execute(select(Tag).where(Tag.value == body.value)).scalar_one_or_none()
        if existing is not None and existing.enabled:
            raise HTTPException(
                status_code=409,
                detail={"message": "tag already enabled", "hint": "use /api/barrage/{id}/vote-tag"},
            )
        if existing is None:
            s.add(
                Tag(
                    value=body.value,
                    label=body.label,
                    icon_url=None,
                    sort=999,
                    enabled=False,
                    proposer_uid=resolved_uid,
                    proposer_ip_hash=ip_h,
                    proposed_at=datetime.utcnow(),
                )
            )
            s.commit()
        # 给 proposer 投一票（pending tag 计票不结算）
        s.add(
            BarrageTagVote(
                barrage_id=barrage_id,
                tag_value=body.value,
                voter_uid=resolved_uid,
                voter_ip_hash=ip_h,
                ts=datetime.utcnow(),
            )
        )
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
        count = vote_count(s, barrage_id, body.value)
        return {
            "data": {
                "tag": body.value,
                "label": body.label,
                "count": count,
                "threshold": vote_threshold(),
                "pending_approval": True,
            }
        }


@router.delete("/submission/{barrage_id}/withdraw")
def withdraw(barrage_id: int, request: Request) -> dict:
    """60s 内可撤回自己刚发的稿。只校验 cookie HMAC + IP 一致 + 未过期。

    管理员状态完全不参与判断（即使 admin 已审/已软删，物理 DELETE 都是幂等的）。
    """
    cookie = request.cookies.get(f"sb_recent_{barrage_id}")
    if not cookie:
        raise HTTPException(status_code=404, detail="no withdraw token")
    ip_h = ip_hash(extract_ip(request))
    expires_at = _hmac_verify(cookie, barrage_id, ip_h)
    if expires_at is None:
        raise HTTPException(status_code=403, detail="invalid withdraw token")
    if int(time.time()) > expires_at:
        raise HTTPException(status_code=410, detail="withdraw window expired")
    with _db.SessionLocal() as s:
        row = s.execute(select(Barrage).where(Barrage.id == barrage_id)).scalar_one_or_none()
        if row is None:
            # 已被删除（admin 软删后又被清理 / 重复撤回），幂等返回
            return {"data": {"id": barrage_id, "already_gone": True}}
        s.delete(row)
        s.commit()
    return {"data": {"id": barrage_id, "withdrawn": True}}
