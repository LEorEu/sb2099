"""submission.evaluate：双 action 规则，block 优先于 pending。"""
from __future__ import annotations

import pytest

from sb2099.submission import evaluate


def test_no_rules_is_ok():
    assert evaluate("hello", None).action == "ok"
    assert evaluate("hello", []).action == "ok"


def test_keyword_block():
    v = evaluate("加微信领奖", [{"type": "keyword", "pattern": "加微信", "action": "block"}])
    assert v.action == "block"
    assert v.matched_pattern == "加微信"


def test_keyword_pending():
    v = evaluate("看广告吗", [{"type": "keyword", "pattern": "广告", "action": "pending"}])
    assert v.action == "pending"


def test_regex_block_with_inline_flag():
    rules = [{"type": "regex", "pattern": r"(?i)v\w{2,}", "action": "block"}]
    assert evaluate("我V信号是 V123ABC", rules).action == "block"


def test_block_overrides_pending_regardless_of_order():
    """同一内容同时命中 block 和 pending → 走 block。"""
    rules = [
        {"type": "keyword", "pattern": "广告", "action": "pending"},
        {"type": "keyword", "pattern": "加微信", "action": "block"},
    ]
    v = evaluate("广告 加微信", rules)
    assert v.action == "block"


def test_invalid_regex_skipped():
    """坏正则被静默跳过，不抛异常。"""
    rules = [{"type": "regex", "pattern": "[unclosed", "action": "block"}]
    assert evaluate("anything", rules).action == "ok"


def test_unknown_type_skipped():
    rules = [{"type": "xpath", "pattern": "//x", "action": "block"}]
    assert evaluate("anything", rules).action == "ok"


def test_empty_content_no_match():
    rules = [{"type": "keyword", "pattern": "x", "action": "block"}]
    assert evaluate("", rules).action == "ok"
