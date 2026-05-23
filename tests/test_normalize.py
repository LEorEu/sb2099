"""normalize() 单测，覆盖 P1-1 冻结的 6 条规则。"""
from __future__ import annotations

import pytest

from sb2099.normalize import normalize


@pytest.mark.parametrize(
    "raw, expected",
    [
        # 1) 全角数字字母 → 半角
        ("ＡＢＣ１２３", "ABC123"),
        # 1) 全角标点 → 半角（汉字不动，不补空格）
        ("好啊，真的！", "好啊,真的!"),
        # 2) 零宽字符清理（U+200B 在"机"和"器"之间）
        ("机​器", "机器"),
        ("打‌rl", "打rl"),
        # 3) 空白合并 + strip
        ("  hello   world  ", "hello world"),
        ("tab\there\nthere", "tab here there"),
        # 3) 全角空格也算空白
        ("好的　很好", "好的 很好"),
        # 4) emoji 保留
        ("哦🐍哦", "哦🐍哦"),
        # 5) 繁简不归一（"鸭" 与 "鴨" 应当保留差异）
        ("打鸭", "打鸭"),
        ("打鴨", "打鴨"),
        # 6) 大小写不归一
        ("GG", "GG"),
        ("gg", "gg"),
        # 综合：全角+零宽+空白
        ("　ＡＢ​cd  ｅｆ　", "ABcd ef"),
        # 空字符串
        ("", ""),
    ],
)
def test_normalize(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


def test_normalize_dedup_targets():
    """零宽剥离 + 全/半角统一 → 应当折叠到同一 content_norm。"""
    a = normalize("打​rl")    # 零宽
    b = normalize("打ｒｌ")    # 全角字母
    c = normalize("打​ｒｌ")  # 零宽 + 全角
    assert a == b == c == "打rl"


def test_normalize_keeps_case_distinct():
    """大小写不归一：去重不应合并。"""
    assert normalize("GG") != normalize("gg")
