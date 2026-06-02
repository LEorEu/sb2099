"""观众互动写入：复制计数 / 不合适反馈 / 标签投票 / 标签提议。"""
from __future__ import annotations

import re
import secrets
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from ... import db as _db
from ...models import Barrage, BarrageReport, BarrageTagVote, DailyHot, Tag
from ...ratelimit import extract_ip, ip_hash, limiter, rate_for
from ...tag_voting import settle_tag, vote_count, vote_threshold
from ._common import resolve_submitter_uid

router = APIRouter(prefix="/api")

_TAG_VALUE_RE = re.compile(r"^[0-9A-Za-z]{1,8}$")


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
        resolved_uid = resolve_submitter_uid(s, body.voter_uid)
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


def _gen_tag_value(session) -> str:
    """给新候选标签分配一个唯一的不透明内部 id（用户不可见，仅作主键/CSV 引用）。

    标签对人的身份是 label；value 只是内部 id，因此服务端生成、不再由前端编造，
    避免「同名标签因 value 不同而无法去重」。'u' + 6 位 hex，符合 ^[0-9A-Za-z]{1,8}$。
    """
    for _ in range(20):
        v = "u" + secrets.token_hex(3)
        if session.get(Tag, v) is None:
            return v
    raise HTTPException(status_code=500, detail="could not allocate tag value")


class ProposeTagIn(BaseModel):
    label: str = Field(min_length=1, max_length=32)
    voter_uid: str | None = None

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
    """按「标签名（label）」提议新标签并给当前 barrage 投一票。

    去重以 label 为准（value 是内部 id，由服务端分配）：
    - 同名「启用」标签已存在 → 409（提示直接投它，别重复提议）
    - 同名「候选」标签已存在 → 复用它，给当前 barrage 加一票
      （于是多人 / 多条提议同一名字会累加到同一候选，票数/关联成为真实信号）
    - 都没有 → 新建候选（enabled=False，value 服务端生成）+ 投一票
    """
    with _db.SessionLocal() as s:
        b = s.execute(
            select(Barrage).where(Barrage.id == barrage_id, Barrage.status == "active")
        ).scalar_one_or_none()
        if b is None:
            raise HTTPException(status_code=404, detail="barrage not found")
        ip_h = ip_hash(extract_ip(request))
        resolved_uid = resolve_submitter_uid(s, body.voter_uid)

        same_name = s.execute(select(Tag).where(Tag.label == body.label)).scalars().all()
        if any(t.enabled for t in same_name):
            raise HTTPException(
                status_code=409,
                detail={"message": "tag already enabled", "hint": "该标签已存在，直接点它投票即可"},
            )
        candidate = next((t for t in same_name if not t.enabled), None)
        if candidate is None:
            value = _gen_tag_value(s)
            s.add(
                Tag(
                    value=value,
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
        else:
            value = candidate.value

        # 给当前 barrage 投一票（候选 tag 计票不结算；同人同条重复提议幂等）
        s.add(
            BarrageTagVote(
                barrage_id=barrage_id,
                tag_value=value,
                voter_uid=resolved_uid,
                voter_ip_hash=ip_h,
                ts=datetime.utcnow(),
            )
        )
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
        count = vote_count(s, barrage_id, value)
        return {
            "data": {
                "tag": value,
                "label": body.label,
                "count": count,
                "threshold": vote_threshold(),
                "pending_approval": True,
            }
        }
