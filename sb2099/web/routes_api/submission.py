"""投稿写入：提交 / 从热榜提升入库 / 60s 撤回，及撤回窗口的 HMAC cookie 工具。"""
from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ... import db as _db
from ...config import get_settings
from ...models import Barrage, DailyHot, Tag
from ...normalize import normalize
from ...ratelimit import extract_ip, ip_hash, limiter, rate_for
from ...settings import settings_cache
from ...submission import evaluate, review_uid
from ._common import resolve_submitter_uid

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


# ---- 共用小工具 -----------------------------------------------------------


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


def _enabled_tag_values() -> set[str]:
    with _db.SessionLocal() as s:
        return set(
            s.execute(select(Tag.value).where(Tag.enabled.is_(True))).scalars().all()
        )


def _enforce_submit_rate(ip_h: str, signed: bool) -> None:
    """按是否已署名分桶限流：已选有效用户更宽松，匿名更严。两桶独立计数。

    用 slowapi 底层 strategy 手动打点（共用同一存储），因为限额取决于请求体里的
    submitter_uid，装饰器在拿到 body 前无法区分。
    """
    from limits import RateLimitItemPerHour

    if signed:
        n = int(settings_cache.get("ratelimit_submit_signed_per_hour_per_ip", 30) or 30)
        bucket = "submit_signed"
    else:
        n = int(settings_cache.get("ratelimit_submit_per_hour_per_ip", 5) or 5)
        bucket = "submit_anon"
    item = RateLimitItemPerHour(max(1, n))
    if not limiter.limiter.hit(item, bucket, ip_h):
        raise HTTPException(status_code=429, detail="submit rate limit exceeded")


@router.post("/barrage", status_code=201)
def submit_barrage(request: Request, response: Response, body: SubmitIn) -> dict:
    # 限流：先判定是否署名（uid 在名册里），匿名 5/h、已署名 30/h，独立分桶
    ip_h_for_limit = ip_hash(extract_ip(request))
    with _db.SessionLocal() as _s:
        _signed = resolve_submitter_uid(_s, body.submitter_uid) is not None
    _enforce_submit_rate(ip_h_for_limit, _signed)

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
        resolved_uid = resolve_submitter_uid(s, body.submitter_uid)
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
        from ...normalize import strip_decorations
        from ...ingest.aggregator import normalized_suffix_strips, normalized_cut_markers
        content = strip_decorations(
            hot.content_sample, normalized_suffix_strips(), normalized_cut_markers()
        )
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
        resolved_uid = resolve_submitter_uid(s, body.submitter_uid)
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
