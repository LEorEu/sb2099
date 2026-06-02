"""归一化函数：把弹幕原文映射为 `content_norm`，用于去重 / 热门聚合 / 跨板块提升。

规则（2026-05-28 更新）：

1. 全角 → 半角：数字、字母、常用标点 `,` `.` `!` `?` `(` `)` `:` `;`（汉字不动）
2. 零宽字符清理：剥离 U+200B / 200C / 200D / 2060 / FEFF
3. 空白合并：连续空白（含 \\t / \\n / 全角空格 U+3000）合并为单空格，首尾 strip
4. emoji 保留（不剥离）
5. 繁简不统一
6. 大小写不归一（"GG" 与 "gg" 视为不同）
6.5 **截断标记**（可选，传入 `cut_markers`）：在尾缀剥除/折叠之前，若串中出现任一
   标记词，则从其首次出现处截到结尾（标记前无内容则不截）。用于 douyuex 等插件那种
   「固定前缀 + 千变万化装饰」的尾巴（`Oᴗoಣ喵~` / `Oᴗoಣですわ` / `Oᴗoಣ♥…`），
   只需配 `Oᴗoಣ` 一个标记即可全收，避免穷举尾缀变体。标记应已规范化后传入。
7. **尾缀剥除**（可选，传入 `suffixes`）：在重复段折叠之前，若串尾命中任一尾缀词
   则剥掉，可连续剥多个；剥到只剩尾缀本身则停（保底不剥空）。用于 douyuex 等插件
   给复制弹幕自动追加的自定义尾缀（如 `喵` / `Oᴗoಣ`），使去掉尾缀后内容相同的
   弹幕聚合为同一 `content_norm`。尾缀词应由调用方先用 `normalize()`（不带尾缀）
   规范化为规范形再传入。
8. **重复段折叠**：若整串恰好等于某子串 p 的 n 次重复 (n>=2, len(p)>=2)，折叠为 p。
   例：`宝宝你好可爱啊宝宝你好可爱啊` → `宝宝你好可爱啊`。仅当严格周期才折叠。

纯函数，无外部依赖（尾缀表由调用方从 setting 读出后传入）。改规则需同步修改
头部 docstring 与单测契约。
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

__all__ = ["normalize", "strip_decorations"]


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


def _apply_cut_markers(s: str, markers: Sequence[str]) -> str:
    """截断标记:串中只要出现标记词,就从其(首次出现)位置截到结尾。

    用于 douyuex 等插件追加的「固定前缀 + 千变万化装饰」尾巴
    (如 `Oᴗoಣ喵~` / `Oᴗoಣですわ` / `Oᴗoಣ♥...`),只需配 `Oᴗoಣ` 一个标记即可全收。
    保底:标记前无内容(idx==0)则不截,避免把整串截空。markers 应为规范形。
    """
    if not markers:
        return s
    for m in markers:
        if not m:
            continue
        i = s.find(m)
        if i > 0:
            s = s[:i].rstrip()
    return s


def _strip_suffixes(s: str, suffixes: Sequence[str]) -> str:
    """连续剥除串尾命中的尾缀词;剥到只剩尾缀本身则停(保底不剥空)。

    suffixes 应已是规范形(调用方用 normalize() 处理过)。剥除后顺手 rstrip
    清掉尾缀前可能残留的空白。
    """
    if not suffixes:
        return s
    changed = True
    while changed and s:
        changed = False
        for suf in suffixes:
            if suf and s != suf and s.endswith(suf):
                s = s[: -len(suf)].rstrip()
                changed = True
                break
    return s


def strip_decorations(s: str, suffixes: Sequence[str] = (), cut_markers: Sequence[str] = ()) -> str:
    """清理「展示用样本」：砍掉 douyuex 截断标记整条尾巴 + 裸尾缀词，
    但保留 emoji / 重复段 / 大小写（不折叠、不做全半角归一），读起来自然。

    与 `normalize()` 不同——后者是给去重/聚合用的规范键；本函数只为 UI 展示去掉
    尾巴噪声。suffixes / cut_markers 应为规范形（调用方用 normalize() 处理过）。
    """
    if not s:
        return ""
    s = _apply_cut_markers(s.rstrip(), cut_markers)
    s = _strip_suffixes(s, suffixes)
    return s


def normalize(s: str, suffixes: Sequence[str] = (), cut_markers: Sequence[str] = ()) -> str:
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

    # 4a) 截断标记（先于尾缀剥除与折叠：把 douyuex 那种「标记+任意装饰」整条尾巴砍掉）
    collapsed = _apply_cut_markers(collapsed, cut_markers)

    # 4b) 尾缀剥除（在折叠之前：尾缀追加在重复内容之后，先剥才能还原周期）
    collapsed = _strip_suffixes(collapsed, suffixes)

    # 5) 重复段折叠（必须在空白合并与尾缀剥除之后）
    return _collapse_repeat(collapsed)
