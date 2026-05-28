"""归一化函数：把弹幕原文映射为 `content_norm`，用于去重 / 热门聚合 / 跨板块提升。

规则（2026-05-28 更新）：

1. 全角 → 半角：数字、字母、常用标点 `,` `.` `!` `?` `(` `)` `:` `;`（汉字不动）
2. 零宽字符清理：剥离 U+200B / 200C / 200D / 2060 / FEFF
3. 空白合并：连续空白（含 \\t / \\n / 全角空格 U+3000）合并为单空格，首尾 strip
4. emoji 保留（不剥离）
5. 繁简不统一
6. 大小写不归一（"GG" 与 "gg" 视为不同）
7. **重复段折叠**：若整串恰好等于某子串 p 的 n 次重复 (n>=2, len(p)>=2)，折叠为 p。
   例：`宝宝你好可爱啊宝宝你好可爱啊` → `宝宝你好可爱啊`。仅当严格周期才折叠，
   防止 `宝宝你好可爱啊Oᴗoಣ` 这种带尾缀的被误聚合。

纯函数，无外部依赖。改规则需同步修改头部 docstring 与单测契约。
"""
from __future__ import annotations

import re
import unicodedata

__all__ = ["normalize"]


_ZERO_WIDTH = {
    "​",  # ZERO WIDTH SPACE
    "‌",  # ZWNJ
    "‍",  # ZWJ
    "⁠",  # WORD JOINER
    "﻿",  # BOM / ZWNBSP
}

_FULLWIDTH_PUNCT = {
    "，": ",",
    "．": ".",
    "！": "!",
    "？": "?",
    "（": "(",
    "）": ")",
    "：": ":",
    "；": ";",
}

_WS_RE = re.compile(r"\s+")


def _collapse_repeat(s: str) -> str:
    """如果 s 是某个长度 ≥ 2 的子串 p 重复 ≥ 2 次的结果,返回最短的 p;否则返回 s。

    例:
      "晚安晚安晚安"  -> "晚安"           (p_len=2, n=3)
      "宝宝你好可爱啊宝宝你好可爱啊" -> "宝宝你好可爱啊" (p_len=7, n=2)
      "🔇😎🔇享受🔇😎🔇享受" -> "🔇😎🔇享受"   (p_len=5, n=2)
      "宝宝你好可爱啊Oᴗoಣ" -> 不动        (无严格周期)
      "啊啊" / "8888" -> 不动             (block 长度 < 2)
    """
    n = len(s)
    if n < 4:  # 至少 2 字符块 × 2 次
        return s
    for p_len in range(2, n // 2 + 1):
        if n % p_len != 0:
            continue
        p = s[:p_len]
        if p * (n // p_len) == s:
            return p
    return s


def normalize(s: str) -> str:
    if not s:
        return ""

    # 1) 零宽字符清理（先于全/半角转换，避免零宽干扰 NFKC 行为）
    cleaned = "".join(ch for ch in s if ch not in _ZERO_WIDTH)

    # 2) 全角 → 半角（仅数字、字母、上述标点）
    out_chars: list[str] = []
    for ch in cleaned:
        # 标点单独映射，避免 NFKC 把汉字一并改变
        if ch in _FULLWIDTH_PUNCT:
            out_chars.append(_FULLWIDTH_PUNCT[ch])
            continue
        code = ord(ch)
        # 全角数字 / 字母范围：U+FF10-FF19, U+FF21-FF3A, U+FF41-FF5A
        if 0xFF10 <= code <= 0xFF19 or 0xFF21 <= code <= 0xFF3A or 0xFF41 <= code <= 0xFF5A:
            out_chars.append(unicodedata.normalize("NFKC", ch))
        else:
            out_chars.append(ch)
    half = "".join(out_chars)

    # 3) 空白合并 + 首尾 strip（全角空格 U+3000 也算空白；re \s 已覆盖）
    collapsed = _WS_RE.sub(" ", half).strip()

    # 4) 重复段折叠（必须在空白合并之后）
    return _collapse_repeat(collapsed)
