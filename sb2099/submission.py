"""投稿审核 — 纯函数 + 反伪 uid 探测器，供 POST /api/barrage 使用。

两组判断：

1. 内容规则 `evaluate(content, rules)`：基于 setting 表 `submission_review_rules`
   配置的关键词/regex；命中 `block` → 拒收 422，命中 `pending` → 入库 status='pending'。
2. uid 防伪探测器 `review_uid(...)`：基于 setting 表多个阈值；命中任一 → pending。
   - unseen_in_room: 该 uid 在 raw_danmaku 从未出现
   - inactive_Nd:    该 uid 最近 N 天没说话
   - distinct_ip_hashes_N: 同 uid 在窗口期内来自 ≥ N 个不同 ip_hash

调用方依次跑两组，先 block 后 pending 后 active；探测器只判定 pending，不 block。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Literal, NamedTuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Barrage, RawDanmaku
from .settings import settings_cache

__all__ = ["RuleVerdict", "evaluate", "review_uid"]


class RuleVerdict(NamedTuple):
    action: Literal["ok", "block", "pending"]
    matched_pattern: str | None = None


def _match(rule: dict, content: str) -> bool:
    t = rule.get("type")
    pat = rule.get("pattern")
    if not pat or not isinstance(pat, str):
        return False
    if t == "keyword":
        return pat in content
    if t == "regex":
        try:
            return re.search(pat, content) is not None
        except re.error:
            return False
    return False


def evaluate(content: str, rules: list[dict] | None) -> RuleVerdict:
    """先查 block 规则，未命中再查 pending 规则。"""
    if not rules:
        return RuleVerdict("ok")
    # block 优先全扫一遍
    for r in rules:
        if r.get("action") == "block" and _match(r, content):
            return RuleVerdict("block", r.get("pattern"))
    for r in rules:
        if r.get("action") == "pending" and _match(r, content):
            return RuleVerdict("pending", r.get("pattern"))
    return RuleVerdict("ok")


def _utcnow_naive() -> datetime:
    return datetime.utcnow()


def review_uid(
    session: Session,
    submitter_uid: str | None,
    ip_hash: str | None,
) -> tuple[bool, str | None]:
    """uid 维度探测器。返回 (pending?, reason)。

    匿名投稿 (submitter_uid=None) 直接放行。setting 表
    submission_anti_fraud_enabled=False 时全部跳过。
    """
    if not settings_cache.get("submission_anti_fraud_enabled", True):
        return False, None
    if not submitter_uid:
        return False, None

    # 探测器 1: 该 uid 在 raw_danmaku 从未出现
    if settings_cache.get("submission_uid_unseen_blocks", True):
        seen = session.query(RawDanmaku.id).filter_by(uid=submitter_uid).first()
        if seen is None:
            return True, "uid_never_seen_in_room"

    # 探测器 2: 该 uid 最近 N 天没说话
    inactive_days = int(settings_cache.get("submission_uid_inactive_days", 30) or 0)
    if inactive_days > 0:
        cutoff = _utcnow_naive() - timedelta(days=inactive_days)
        last_ts = session.query(func.max(RawDanmaku.ts)).filter_by(uid=submitter_uid).scalar()
        if last_ts is not None and last_ts < cutoff:
            return True, f"uid_inactive_{inactive_days}d"

    # 探测器 3: 同 uid 跨多 IP hash
    window_days = int(settings_cache.get("submission_uid_multi_ip_window_days", 7) or 0)
    threshold = int(settings_cache.get("submission_uid_multi_ip_threshold", 5) or 0)
    if window_days > 0 and threshold > 0:
        window_cutoff = _utcnow_naive() - timedelta(days=window_days)
        rows = session.query(Barrage.submitter_ip_hash).filter(
            Barrage.submitter_uid == submitter_uid,
            Barrage.submit_time >= window_cutoff,
            Barrage.submitter_ip_hash.is_not(None),
        ).distinct().all()
        distinct_hashes = {h for (h,) in rows}
        if ip_hash:
            distinct_hashes.add(ip_hash)
        if len(distinct_hashes) >= threshold:
            return True, f"uid_distinct_ip_hashes_{len(distinct_hashes)}"

    return False, None
