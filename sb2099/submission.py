"""投稿审核规则匹配 — 纯函数，供 POST /api/barrage 使用。

设计文档 P1-3 双 action 决策表（按优先级）：
- 命中任一 `block` 规则 → 拒收 422
- 命中任一 `pending` 规则 → 入库 status='pending'
- 都不命中 → 入库 status='active'

`block` 优先于 `pending`。规则形如 `[{"type":"keyword|regex","pattern":...,"action":"block|pending"}, ...]`。
作用于投稿原文 `content`（非归一化）。
"""
from __future__ import annotations

import re
from typing import Literal, NamedTuple

__all__ = ["RuleVerdict", "evaluate"]


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
